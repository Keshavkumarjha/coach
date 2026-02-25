from django.contrib.auth import authenticate
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .auth_utils import normalize_mobile
from .models import User, OrgMembership, Role, MembershipStatus, BranchJoinRequest, JoinStatus, JoinRole
from apps.orgs.models import Organisation, Branch

try:
    from apps.billing.models import OrganisationSubscription, SubscriptionPlan, PlanCode
except Exception:
    OrganisationSubscription = None
    SubscriptionPlan = None
    PlanCode = None


class JWTTokenMixin:
    @staticmethod
    def build_tokens(user: User) -> dict:
        refresh = RefreshToken.for_user(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


class OrganisationSignupSerializer(serializers.Serializer):
    org_name = serializers.CharField(max_length=180)
    owner_name = serializers.CharField(max_length=120)
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_mobile(self, value):
        mobile = normalize_mobile(value)
        if not (10 <= len(mobile) <= 15):
            raise serializers.ValidationError("Invalid mobile number.")
        if User.objects.filter(mobile=mobile).exists():
            # Do not reveal whether the account exists in sensitive flows,
            # but for signup it's ok to be explicit.
            raise serializers.ValidationError("Mobile already registered.")
        return mobile

    def validate_password(self, value):
        # You can enforce stronger rules here.
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        org_name = validated_data["org_name"].strip()
        owner_name = validated_data["owner_name"].strip()
        mobile = validated_data["mobile"]
        password = validated_data["password"]

        user = User.objects.create_user(
            mobile=mobile,
            password=password,
            full_name=owner_name,
            is_active=True,
        )

        base_slug = slugify(org_name)[:160] or "org"
        slug = base_slug
        i = 1
        while Organisation.objects.filter(slug=slug).exists():
            i += 1
            slug = f"{base_slug}-{i}"

        org = Organisation.objects.create(
            name=org_name,
            slug=slug,
            owner_name=owner_name,
            owner_mobile=mobile,
            status="ACTIVE",  # set PENDING if you want manual review
        )

        OrgMembership.objects.create(
            user=user,
            organisation=org,
            role=Role.ORG_OWNER,
            status=MembershipStatus.ACTIVE,
        )

        # Optional: Attach FREE plan automatically
        if SubscriptionPlan and OrganisationSubscription and PlanCode:
            plan = SubscriptionPlan.objects.filter(code=PlanCode.FREE).first()
            if plan:
                OrganisationSubscription.objects.get_or_create(
                    organisation=org,
                    defaults={"plan": plan, "status": "ACTIVE"},
                )

        return {"user": user, "organisation": org}


class LoginSerializer(serializers.Serializer, JWTTokenMixin):
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        mobile = normalize_mobile(attrs.get("mobile"))
        password = attrs.get("password")

        # Don’t reveal if user exists or not (anti-enumeration)
        user = authenticate(mobile=mobile, password=password)
        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "Account is disabled."})

        # approval checks: must have ACTIVE membership or active student/parent profile
        allowed = OrgMembership.objects.filter(user=user, status=MembershipStatus.ACTIVE).exists()
        if hasattr(user, "student_profile") and user.student_profile.is_active_for_login:
            allowed = True
        if hasattr(user, "parent_profile") and user.parent_profile.is_active_for_login:
            allowed = True

        if not allowed:
            raise serializers.ValidationError({"detail": "Account not approved yet."})

        return {
            "user_id": user.id,
            "mobile": user.mobile,
            "full_name": user.full_name,
            **self.build_tokens(user),
        }


class BranchJoinRequestSerializer(serializers.Serializer):
    """
    Student/Parent registers using Branch join code + mobile + password.
    Creates (or reuses) a PENDING join request.
    """
    branch_code = serializers.CharField(max_length=12)
    role = serializers.ChoiceField(choices=JoinRole.choices)
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=120)

    # optional student data:
    admission_no = serializers.CharField(required=False, allow_blank=True, max_length=32)
    roll_no = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate_mobile(self, value):
        mobile = normalize_mobile(value)
        if not (10 <= len(mobile) <= 15):
            raise serializers.ValidationError("Invalid mobile number.")
        return mobile

    @transaction.atomic
    def create(self, validated_data):
        branch_code = validated_data["branch_code"].strip()
        role = validated_data["role"]
        mobile = validated_data["mobile"]
        password = validated_data["password"]
        full_name = validated_data["full_name"].strip()

        branch = Branch.objects.select_related("organisation").filter(public_code=branch_code).first()
        if not branch:
            # don’t reveal too much; still ok to say invalid join code
            raise serializers.ValidationError({"branch_code": "Invalid Branch ID."})

        # Create user if not exists; if exists, require correct password to prevent misuse
        user = User.objects.filter(mobile=mobile).first()
        if user is None:
            user = User.objects.create_user(mobile=mobile, password=password, full_name=full_name, is_active=True)
        else:
            if not user.check_password(password):
                raise serializers.ValidationError({"detail": "Invalid credentials."})

        # Create pending request (idempotent)
        req, created = BranchJoinRequest.objects.get_or_create(
            branch=branch,
            organisation=branch.organisation,
            role=role,
            mobile=mobile,
            status=JoinStatus.PENDING,
            defaults={
                "full_name": full_name,
                "admission_no": validated_data.get("admission_no", ""),
                "roll_no": validated_data.get("roll_no", ""),
            },
        )
        if not created:
            # update name/admission if user re-submits
            changed = False
            if full_name and req.full_name != full_name:
                req.full_name = full_name
                changed = True
            if role == JoinRole.STUDENT:
                adm = validated_data.get("admission_no", "")
                rn = validated_data.get("roll_no", "")
                if adm and req.admission_no != adm:
                    req.admission_no = adm
                    changed = True
                if rn and req.roll_no != rn:
                    req.roll_no = rn
                    changed = True
            if changed:
                req.save(update_fields=["full_name", "admission_no", "roll_no", "updated_at"])

        return req