from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from apps.common.tenant import get_tenant_context
from apps.assessments.models import (
    StudyMaterial,
    Homework,
    HomeworkSubmission,
    HomeworkStatus,
    HomeworkSubmissionStatus,
    Test,
    StudentTestResult,
    TestStatus,
)
from apps.academics.models import BatchEnrollment, EnrollmentStatus


class StudyMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudyMaterial
        fields = [
            "id",
            "batch",
            "title",
            "description",
            "file",
            "link_url",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        ctx = get_tenant_context(request)
        return StudyMaterial.objects.create(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=request.user,
            **validated_data,
        )


class HomeworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Homework
        fields = [
            "id",
            "batch",
            "subject",
            "title",
            "description",
            "due_date",
            "status",
            "attachment",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        ctx = get_tenant_context(request)
        return Homework.objects.create(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=request.user,
            **validated_data,
        )


class HomeworkSubmissionCreateSerializer(serializers.Serializer):
    homework_id = serializers.IntegerField()
    text_answer = serializers.CharField(required=False, allow_blank=True)
    file_answer = serializers.FileField(required=False)

    @transaction.atomic
    def create(self, vd):
        request = self.context["request"]
        ctx = get_tenant_context(request)

        student = getattr(request.user, "student_profile", None)
        if not student:
            raise serializers.ValidationError({"detail": "Student login required."})

        hw = Homework.objects.filter(
            id=vd["homework_id"],
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).select_related("batch").first()
        if not hw:
            raise serializers.ValidationError({"homework_id": "Invalid homework."})

        # Must be enrolled in hw.batch
        enrolled = BatchEnrollment.objects.filter(
            student=student,
            batch=hw.batch,
            status=EnrollmentStatus.ACTIVE,
        ).exists()
        if not enrolled:
            raise serializers.ValidationError({"detail": "Not enrolled in this batch."})

        sub, created = HomeworkSubmission.objects.update_or_create(
            homework=hw,
            student=student,
            defaults={
                "text_answer": vd.get("text_answer", ""),
                "file_answer": vd.get("file_answer"),
                "status": HomeworkSubmissionStatus.SUBMITTED,
            },
        )
        return sub


class HomeworkSubmissionSerializer(serializers.ModelSerializer):
    student_public_id = serializers.CharField(source="student.public_id", read_only=True)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)

    class Meta:
        model = HomeworkSubmission
        fields = [
            "id",
            "homework",
            "student_public_id",
            "student_name",
            "text_answer",
            "file_answer",
            "status",
            "marks",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "student_public_id", "student_name"]


class TestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Test
        fields = [
            "id",
            "batch",
            "subject",
            "name",
            "test_type",
            "scheduled_on",
            "start_time",
            "duration_min",
            "total_marks",
            "passing_marks",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        request = self.context["request"]
        ctx = get_tenant_context(request)
        return Test.objects.create(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=request.user,
            **validated_data,
        )


class StudentTestResultUpsertSerializer(serializers.Serializer):
    test_id = serializers.IntegerField()
    results = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate(self, attrs):
        for r in attrs["results"]:
            if "student_public_id" not in r or "marks_obtained" not in r:
                raise serializers.ValidationError("Each result needs student_public_id and marks_obtained.")
        return attrs


class StudentTestResultSerializer(serializers.ModelSerializer):
    student_public_id = serializers.CharField(source="student.public_id", read_only=True)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    test_name = serializers.CharField(source="test.name", read_only=True)

    class Meta:
        model = StudentTestResult
        fields = [
            "id",
            "test",
            "test_name",
            "student_public_id",
            "student_name",
            "marks_obtained",
            "grade",
            "remarks",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "student_public_id", "student_name", "test_name"]