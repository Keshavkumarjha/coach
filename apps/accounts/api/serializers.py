from __future__ import annotations

from django.contrib.auth import authenticate
from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.auth_utils import normalize_mobile
from apps.accounts.models import User, OrgMembership, Role, MembershipStatus, BranchJoinRequest, JoinRole, JoinStatus
from apps.orgs.models import Organisation, Branch


class TokenMixin:
    @staticmethod
    def tokens_for_user(user: User) -> dict:
        refresh = RefreshToken.for_user(user)
        return {"access": str(refresh.access_token), "refresh": str(refresh)}


class OrgSignupSerializer(serializers.Serializer, TokenMixin):
    org_name = serializers.CharField(max_length=180)
    owner_name = serializers.CharField(max_length=120)
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_mobile(self, v):
        m = normalize_mobile(v)
        if not (10 <= len(m) <= 15):
            raise serializers.ValidationError("Invalid mobile number.")
        if User.objects.filter(mobile=m).exists():
            raise serializers.ValidationError("Mobile already registered.")
        return m

    @transaction.atomic
    def create(self, vd):
        org_name = vd["org_name"].strip()
        owner_name = vd["owner_name"].strip()
        mobile = vd["mobile"]
        password = vd["password"]

        user = User.objects.create_user(mobile=mobile, password=password, full_name=owner_name, is_active=True)

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
            status="ACTIVE",
        )

        OrgMembership.objects.create(
            user=user,
            organisation=org,
            role=Role.ORG_OWNER,
            status=MembershipStatus.ACTIVE,
        )

        return {"user": user, "org": org, **self.tokens_for_user(user)}


class LoginSerializer(serializers.Serializer, TokenMixin):
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        mobile = normalize_mobile(attrs.get("mobile"))
        password = attrs.get("password")

        user = authenticate(mobile=mobile, password=password)
        if not user:
            # generic message
            raise serializers.ValidationError({"detail": "Invalid credentials."})
        if not user.is_active:
            raise serializers.ValidationError({"detail": "Account disabled."})

        # Must have at least one ACTIVE membership OR approved student/parent profile
        allowed = OrgMembership.objects.filter(user=user, status=MembershipStatus.ACTIVE).exists()
        if hasattr(user, "student_profile") and user.student_profile.is_active_for_login:
            allowed = True
        if hasattr(user, "parent_profile") and user.parent_profile.is_active_for_login:
            allowed = True
        if not allowed:
            raise serializers.ValidationError({"detail": "Not approved yet."})

        memberships = list(
            OrgMembership.objects.filter(user=user, status=MembershipStatus.ACTIVE)
            .select_related("organisation", "branch")
            .values(
                "organisation__public_id",
                "organisation__name",
                "branch__public_id",
                "branch__name",
                "role",
            )
        )

        return {
            "user": {"mobile": user.mobile, "full_name": user.full_name},
            "memberships": memberships,
            **self.tokens_for_user(user),
        }


class ForgotPasswordSerializer(serializers.Serializer):
    mobile = serializers.CharField()

    def validate_mobile(self, v):
        m = normalize_mobile(v)
        if not (10 <= len(m) <= 15):
            raise serializers.ValidationError("Invalid mobile.")
        # Do not reveal user existence.
        return m


class ResetPasswordSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_mobile(self, v):
        m = normalize_mobile(v)
        if not (10 <= len(m) <= 15):
            raise serializers.ValidationError("Invalid mobile.")
        return m


class BranchJoinRequestSerializer(serializers.Serializer):
    branch_code = serializers.CharField(max_length=12)
    role = serializers.ChoiceField(choices=JoinRole.choices)
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=120)

    admission_no = serializers.CharField(required=False, allow_blank=True, max_length=32)
    roll_no = serializers.CharField(required=False, allow_blank=True, max_length=20)

    def validate_mobile(self, v):
        m = normalize_mobile(v)
        if not (10 <= len(m) <= 15):
            raise serializers.ValidationError("Invalid mobile number.")
        return m

    @transaction.atomic
    def create(self, vd):
        branch = Branch.objects.select_related("organisation").filter(public_code=vd["branch_code"]).first()
        if not branch:
            raise serializers.ValidationError({"branch_code": "Invalid Branch ID."})

        mobile = vd["mobile"]
        password = vd["password"]
        full_name = vd["full_name"].strip()

        user = User.objects.filter(mobile=mobile).first()
        if user is None:
            user = User.objects.create_user(mobile=mobile, password=password, full_name=full_name, is_active=True)
        else:
            if not user.check_password(password):
                raise serializers.ValidationError({"detail": "Invalid credentials."})

        req, _ = BranchJoinRequest.objects.get_or_create(
            organisation=branch.organisation,
            branch=branch,
            role=vd["role"],
            mobile=mobile,
            status=JoinStatus.PENDING,
            defaults={
                "full_name": full_name,
                "admission_no": vd.get("admission_no", ""),
                "roll_no": vd.get("roll_no", ""),
            },
        )
        return req