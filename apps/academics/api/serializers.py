from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from apps.accounts.auth_utils import normalize_mobile
from apps.accounts.models import User, OrgMembership, Role, MembershipStatus
from apps.common.tenant import get_tenant_context
from apps.orgs.models import Branch
from apps.academics.models import (
    Batch,
    StudentProfile,
    TeacherProfile,
    BatchEnrollment,
    EnrollmentStatus,
    Subject,
    TimeTableSlot,
)


class BatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Batch
        fields = [
            "id",
            "name",
            "code",
            "status",
            "start_time",
            "end_time",
            "days_of_week",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TeacherCreateSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=120)
    employee_id = serializers.CharField(required=False, allow_blank=True, max_length=32)
    designation = serializers.CharField(required=False, allow_blank=True, max_length=60)

    def validate_mobile(self, v):
        m = normalize_mobile(v)
        if not (10 <= len(m) <= 15):
            raise serializers.ValidationError("Invalid mobile number.")
        return m

    @transaction.atomic
    def create(self, vd):
        request = self.context["request"]
        ctx = get_tenant_context(request)

        mobile = vd["mobile"]
        password = vd["password"]
        full_name = vd["full_name"].strip()

        # Create or reuse user
        user = User.objects.filter(mobile=mobile).first()
        if user is None:
            user = User.objects.create_user(mobile=mobile, password=password, full_name=full_name, is_active=True)
        else:
            # If user exists but admin provides password, update it to allow login
            user.full_name = full_name or user.full_name
            user.set_password(password)
            user.save(update_fields=["full_name", "password", "updated_at"])

        # Membership
        OrgMembership.objects.update_or_create(
            user=user,
            organisation=ctx.organisation,
            branch=ctx.branch,
            role=Role.TEACHER,
            defaults={"status": MembershipStatus.ACTIVE},
        )

        teacher, _ = TeacherProfile.objects.update_or_create(
            user=user,
            organisation=ctx.organisation,
            branch=ctx.branch,
            defaults={
                "employee_id": vd.get("employee_id", ""),
                "designation": vd.get("designation", ""),
                "is_active_for_login": True,
            },
        )
        return teacher


class TeacherSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(source="user.mobile", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = TeacherProfile
        fields = [
            "public_id",
            "mobile",
            "full_name",
            "employee_id",
            "designation",
            "is_active_for_login",
            "created_at",
        ]
        read_only_fields = ["public_id", "mobile", "full_name", "created_at"]


class StudentCreateSerializer(serializers.Serializer):
    mobile = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=120)

    admission_no = serializers.CharField(max_length=32)
    roll_no = serializers.CharField(required=False, allow_blank=True, max_length=20)

    # optional enrollment
    batch_id = serializers.IntegerField(required=False)

    def validate_mobile(self, v):
        m = normalize_mobile(v)
        if not (10 <= len(m) <= 15):
            raise serializers.ValidationError("Invalid mobile number.")
        return m

    @transaction.atomic
    def create(self, vd):
        request = self.context["request"]
        ctx = get_tenant_context(request)

        mobile = vd["mobile"]
        password = vd["password"]
        full_name = vd["full_name"].strip()

        user = User.objects.filter(mobile=mobile).first()
        if user is None:
            user = User.objects.create_user(mobile=mobile, password=password, full_name=full_name, is_active=True)
        else:
            user.full_name = full_name or user.full_name
            user.set_password(password)
            user.save(update_fields=["full_name", "password", "updated_at"])

        OrgMembership.objects.update_or_create(
            user=user,
            organisation=ctx.organisation,
            branch=ctx.branch,
            role=Role.STUDENT,
            defaults={"status": MembershipStatus.ACTIVE},
        )

        student, _ = StudentProfile.objects.update_or_create(
            user=user,
            organisation=ctx.organisation,
            branch=ctx.branch,
            defaults={
                "admission_no": vd["admission_no"].strip(),
                "roll_no": vd.get("roll_no", ""),
                # admin-created student is approved for login:
                "is_active_for_login": True,
            },
        )

        batch_id = vd.get("batch_id")
        if batch_id:
            batch = Batch.objects.filter(id=batch_id, branch=ctx.branch, organisation=ctx.organisation).first()
            if not batch:
                raise serializers.ValidationError({"batch_id": "Invalid batch for this branch."})

            BatchEnrollment.objects.update_or_create(
                batch=batch,
                student=student,
                defaults={"status": EnrollmentStatus.ACTIVE},
            )

        return student


class StudentSerializer(serializers.ModelSerializer):
    mobile = serializers.CharField(source="user.mobile", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            "public_id",
            "mobile",
            "full_name",
            "admission_no",
            "roll_no",
            "is_active_for_login",
            "created_at",
        ]
        read_only_fields = ["public_id", "mobile", "full_name", "created_at"]


class EnrollmentSerializer(serializers.ModelSerializer):
    batch_name = serializers.CharField(source="batch.name", read_only=True)
    batch_code = serializers.CharField(source="batch.code", read_only=True)

    class Meta:
        model = BatchEnrollment
        fields = ["id", "batch", "batch_name", "batch_code", "status", "joined_on", "left_on", "created_at"]
        read_only_fields = ["id", "created_at"]


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


class TimeTableSlotSerializer(serializers.ModelSerializer):
    teacher_public_id = serializers.CharField(source="teacher.public_id", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    batch_name = serializers.CharField(source="batch.name", read_only=True)

    class Meta:
        model = TimeTableSlot
        fields = [
            "id",
            "batch",
            "batch_name",
            "weekday",
            "start_time",
            "end_time",
            "subject",
            "subject_name",
            "teacher",
            "teacher_public_id",
            "room",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "batch_name", "subject_name", "teacher_public_id"]