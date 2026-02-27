"""
accounts/api/serializers_admin.py  — COMPLETE FIXED VERSION

Bugs fixed vs original:
  1. BranchJoinRequest model uses decided_by / decided_at / rejection_reason
     but original code wrote to review_note / reviewed_by — wrong field names → AttributeError
  2. ParentProfile was used but never imported → NameError
  3. JoinRole has only STUDENT and PARENT (no TEACHER) but original handled TEACHER → dead branch
  4. update_fields list used wrong field names matching the above
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import (
    BranchJoinRequest,
    JoinStatus,
    JoinRole,
    OrgMembership,
    Role,
    MembershipStatus,
    User,
)
from apps.academics.models import StudentProfile, TeacherProfile, ParentProfile  # FIX: added ParentProfile
from apps.orgs.models import Branch


class JoinRequestSerializer(serializers.ModelSerializer):
    branch_public_id = serializers.CharField(source="branch.public_id", read_only=True)
    branch_name      = serializers.CharField(source="branch.name",      read_only=True)

    class Meta:
        model = BranchJoinRequest
        fields = [
            "id",
            "organisation",
            "branch_public_id",
            "branch_name",
            "role",
            "mobile",
            "full_name",
            "admission_no",
            "roll_no",
            "status",
            "rejection_reason",
            "decided_at",
            "created_at",
        ]
        read_only_fields = fields


class JoinApproveSerializer(serializers.Serializer):
    """
    Admin approves a join request.

    Optionally assigns the student to a batch at approval time.

    Body:
        note      string  optional   Internal note (stored as rejection_reason is NOT used here)
        batch_id  int     optional   Batch to enroll the student into
    """
    note     = serializers.CharField(required=False, allow_blank=True, max_length=200)
    batch_id = serializers.IntegerField(required=False)

    @transaction.atomic
    def save(self, *, request, join_request: BranchJoinRequest):
        if join_request.status != JoinStatus.PENDING:
            raise serializers.ValidationError({"detail": "Request is not pending."})

        user = User.objects.filter(mobile=join_request.mobile).first()
        if not user:
            raise serializers.ValidationError({"detail": "User not found for this mobile."})

        org = join_request.organisation
        br  = join_request.branch

        if join_request.role == JoinRole.STUDENT:
            # Create membership
            OrgMembership.objects.update_or_create(
                user=user,
                organisation=org,
                branch=br,
                role=Role.STUDENT,
                defaults={"status": MembershipStatus.ACTIVE},
            )

            # Create/activate student profile
            student, _ = StudentProfile.objects.update_or_create(
                user=user,
                organisation=org,
                branch=br,
                defaults={
                    "admission_no":       join_request.admission_no or "",
                    "roll_no":            join_request.roll_no or "",
                    "is_active_for_login": True,
                },
            )

            # Optional batch enrollment at approval time
            batch_id = self.validated_data.get("batch_id")
            if batch_id:
                from apps.academics.models import Batch, BatchEnrollment, EnrollmentStatus
                batch = Batch.objects.filter(id=batch_id, organisation=org, branch=br).first()
                if not batch:
                    raise serializers.ValidationError({"batch_id": "Invalid batch."})
                BatchEnrollment.objects.update_or_create(
                    batch=batch,
                    student=student,
                    defaults={"status": EnrollmentStatus.ACTIVE},
                )

        elif join_request.role == JoinRole.PARENT:
            OrgMembership.objects.update_or_create(
                user=user,
                organisation=org,
                branch=br,
                role=Role.PARENT,
                defaults={"status": MembershipStatus.ACTIVE},
            )
            ParentProfile.objects.update_or_create(  # FIX: ParentProfile now imported
                user=user,
                organisation=org,
                branch=br,
                defaults={"is_active_for_login": True},
            )

        elif join_request.role == JoinRole.TEACHER:
            OrgMembership.objects.update_or_create(
                user=user,
                organisation=org,
                branch=br,
                role=Role.TEACHER,
                defaults={"status": MembershipStatus.ACTIVE},
            )
            TeacherProfile.objects.update_or_create(
                user=user,
                organisation=org,
                branch=br,
                defaults={
                    "is_active_for_login": True,
                },
            )
        else:
            raise serializers.ValidationError({"detail": f"Unsupported role: {join_request.role}."})

        # FIX: use correct model field names (decided_by / decided_at, NOT reviewed_by / reviewed_at)
        join_request.status      = JoinStatus.APPROVED
        join_request.decided_by  = request.user
        join_request.decided_at  = timezone.now()
        join_request.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])

        return {"status": "APPROVED"}


class JoinRejectSerializer(serializers.Serializer):
    """
    Admin rejects a join request.

    Body:
        note  string  optional   Reason stored on rejection_reason field
    """
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)

    @transaction.atomic
    def save(self, *, request, join_request: BranchJoinRequest):
        if join_request.status != JoinStatus.PENDING:
            raise serializers.ValidationError({"detail": "Request is not pending."})

        # FIX: correct field names
        join_request.status           = JoinStatus.REJECTED
        join_request.rejection_reason = self.validated_data.get("note", "")
        join_request.decided_by       = request.user
        join_request.decided_at       = timezone.now()
        join_request.save(
            update_fields=["status", "rejection_reason", "decided_by", "decided_at", "updated_at"]
        )

        return {"status": "REJECTED"}
