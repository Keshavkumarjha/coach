from __future__ import annotations

from django.db import transaction
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
from apps.academics.models import StudentProfile, TeacherProfile

from apps.orgs.models import Branch


class JoinRequestSerializer(serializers.ModelSerializer):
    branch_public_id = serializers.CharField(source="branch.public_id", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

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
            "created_at",
        ]
        read_only_fields = fields


class JoinApproveSerializer(serializers.Serializer):
    """
    Admin approves join request.
    Can optionally assign a batch_id for student at approval time.
    """
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)
    batch_id = serializers.IntegerField(required=False)

    @transaction.atomic
    def save(self, *, request, join_request: BranchJoinRequest):
        if join_request.status != JoinStatus.PENDING:
            raise serializers.ValidationError({"detail": "Request is not pending."})

        user = User.objects.filter(mobile=join_request.mobile).first()
        if not user:
            raise serializers.ValidationError({"detail": "User not found for this mobile."})

        # Approve + create role profiles + membership
        org = join_request.organisation
        br = join_request.branch

        if join_request.role == JoinRole.STUDENT:
            OrgMembership.objects.update_or_create(
                user=user,
                organisation=org,
                branch=br,
                role=Role.STUDENT,
                defaults={"status": MembershipStatus.ACTIVE},
            )

            st, _ = StudentProfile.objects.update_or_create(
                user=user,
                organisation=org,
                branch=br,
                defaults={
                    "admission_no": join_request.admission_no or "",
                    "roll_no": join_request.roll_no or "",
                    "is_active_for_login": True,
                },
            )

            # Optional: enroll into batch if provided
            batch_id = self.validated_data.get("batch_id")
            if batch_id:
                from apps.academics.models import Batch, BatchEnrollment, EnrollmentStatus
                batch = Batch.objects.filter(id=batch_id, organisation=org, branch=br).first()
                if not batch:
                    raise serializers.ValidationError({"batch_id": "Invalid batch."})
                BatchEnrollment.objects.update_or_create(
                    batch=batch,
                    student=st,
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
            ParentProfile.objects.update_or_create(
                user=user,
                organisation=org,
                branch=br,
                defaults={
                    "is_active_for_login": True,
                },
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
            raise serializers.ValidationError({"detail": "Unsupported role."})

        join_request.status = JoinStatus.APPROVED
        join_request.review_note = self.validated_data.get("note", "")
        join_request.reviewed_by = request.user
        join_request.save(update_fields=["status", "review_note", "reviewed_by", "updated_at"])

        return {"status": "APPROVED"}


class JoinRejectSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)

    @transaction.atomic
    def save(self, *, request, join_request: BranchJoinRequest):
        if join_request.status != JoinStatus.PENDING:
            raise serializers.ValidationError({"detail": "Request is not pending."})

        join_request.status = JoinStatus.REJECTED
        join_request.review_note = self.validated_data.get("note", "")
        join_request.reviewed_by = request.user
        join_request.save(update_fields=["status", "review_note", "reviewed_by", "updated_at"])

        return {"status": "REJECTED"}