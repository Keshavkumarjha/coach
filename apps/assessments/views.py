"""
assessments/api/views.py

Study materials, homework, and test management.

Endpoints
─────────
Study Materials
  GET/POST        /api/materials/             Teacher: create  Student: view
  GET/PATCH/DEL   /api/materials/{id}/

Homework
  GET/POST        /api/homework/
  GET/PATCH/DEL   /api/homework/{id}/
  GET             /api/homework/{id}/submissions/   Teacher: see all submissions
  POST            /api/homework/submit/             Student: submit answer

Tests
  GET/POST        /api/tests/
  GET/PATCH/DEL   /api/tests/{id}/
  GET             /api/tests/{id}/results/          Student: see own result
  POST            /api/tests/upsert-results/        Teacher: save results in bulk
"""
from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet, StatusFilterMixin, BatchFilterMixin
from apps.common.permissions import IsBranchAdmin, IsTeacher, IsStudentOrParent
from apps.assessments.models import (
    Homework,
    HomeworkSubmission,
    StudyMaterial,
    StudentTestResult,
    Test,
)
from apps.academics.models import StudentProfile
from apps.assessments.api.serializers import (
    HomeworkSerializer,
    HomeworkSubmissionCreateSerializer,
    HomeworkSubmissionSerializer,
    StudyMaterialSerializer,
    StudentTestResultSerializer,
    StudentTestResultUpsertSerializer,
    TestSerializer,
)


class StudyMaterialViewSet(BatchFilterMixin, TenantViewSet):
    """
    Study materials per batch.

    Permissions:
        create / update / delete  → IsTeacher
        list / retrieve           → IsStudentOrParent

    Query params:
        ?batch_id=<int>
    """
    serializer_class = StudyMaterialSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = StudyMaterial.objects.select_related("batch").all()
    ordering = ["-created_at"]
    inject_created_by = True

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTeacher()]
        return [IsStudentOrParent()]

    def perform_create(self, serializer):
        ctx = self.get_tenant()
        serializer.save(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=self.request.user,
        )


class HomeworkViewSet(BatchFilterMixin, StatusFilterMixin, TenantViewSet):
    """
    Homework assignments per batch.

    Permissions:
        create / update / delete  → IsTeacher
        list / retrieve           → IsStudentOrParent

    Query params:
        ?batch_id=<int>
        ?status=DRAFT | PUBLISHED | CLOSED

    Custom actions:
        GET  /{id}/submissions/   Teacher: all student submissions for this HW
        POST /submit/             Student: submit answer
    """
    serializer_class = HomeworkSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = Homework.objects.select_related("batch", "subject").all()
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "submissions"}:
            return [IsTeacher()]
        return [IsStudentOrParent()]

    def perform_create(self, serializer):
        ctx = self.get_tenant()
        serializer.save(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=self.request.user,
        )

    @action(detail=True, methods=["get"], url_path="submissions")
    def submissions(self, request, pk=None):
        """
        GET /api/homework/{id}/submissions/
        Returns all student submissions for this homework assignment.
        """
        hw = self.get_object()
        qs = (
            HomeworkSubmission.objects
            .select_related("student", "student__user")
            .filter(homework=hw)
            .order_by("-created_at")
        )
        return Response(HomeworkSubmissionSerializer(qs, many=True).data)

    @action(detail=False, methods=["post"], url_path="submit")
    @transaction.atomic
    def submit(self, request):
        """
        POST /api/homework/submit/
        Student submits (or resubmits) their answer for a homework assignment.

        Body:
            homework_id   int      required
            text_answer   string   optional
            file_answer   file     optional
        """
        serializer = HomeworkSubmissionCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()
        return Response(
            HomeworkSubmissionSerializer(submission).data,
            status=status.HTTP_201_CREATED,
        )


class TestViewSet(BatchFilterMixin, StatusFilterMixin, TenantViewSet):
    """
    Tests/exams per batch.

    Permissions:
        create / update / delete / upsert-results  → IsTeacher
        list / retrieve / results                   → IsStudentOrParent

    Query params:
        ?batch_id=<int>
        ?status=DRAFT | PUBLISHED | COMPLETED

    Custom actions:
        GET  /{id}/results/     Student: view own result for this test
        POST /upsert-results/   Teacher: bulk-save student results
    """
    serializer_class = TestSerializer
    queryset = Test.objects.select_related("batch", "subject").all()
    ordering = ["-scheduled_on", "-created_at"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "upsert_results"}:
            return [IsTeacher()]
        return [IsStudentOrParent()]

    def perform_create(self, serializer):
        ctx = self.get_tenant()
        serializer.save(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=self.request.user,
        )

    @action(detail=True, methods=["get"], url_path="results")
    def results(self, request, pk=None):
        """
        GET /api/tests/{id}/results/
        Returns the authenticated student's result for this test.
        """
        student = getattr(request.user, "student_profile", None)
        if not student:
            return Response(
                {"detail": "Student login required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        test = self.get_object()
        result = StudentTestResult.objects.filter(test=test, student=student).first()
        if not result:
            return Response({}, status=status.HTTP_200_OK)
        return Response(StudentTestResultSerializer(result).data)

    @action(detail=False, methods=["post"], url_path="upsert-results")
    @transaction.atomic
    def upsert_results(self, request):
        """
        POST /api/tests/upsert-results/
        Teacher bulk-saves results for multiple students in one call.

        Body:
            test_id   int     required
            results   list    required  [{ student_public_id, marks_obtained, grade?, remarks? }]
        """
        ctx = self.get_tenant()
        serializer = StudentTestResultUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        test = Test.objects.filter(
            id=serializer.validated_data["test_id"],
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).first()
        if not test:
            return Response(
                {"test_id": "Invalid test."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        public_ids = [r["student_public_id"] for r in serializer.validated_data["results"]]
        student_map = {
            st.public_id: st
            for st in StudentProfile.objects.filter(
                organisation=ctx.organisation,
                branch=ctx.branch,
                public_id__in=public_ids,
            )
        }

        saved = 0
        for row in serializer.validated_data["results"]:
            student = student_map.get(row["student_public_id"])
            if not student:
                continue
            StudentTestResult.objects.update_or_create(
                test=test,
                student=student,
                defaults={
                    "marks_obtained": row.get("marks_obtained", 0),
                    "grade": row.get("grade", ""),
                    "remarks": row.get("remarks", ""),
                    "entered_by": request.user,
                },
            )
            saved += 1

        return Response(
            {"message": "Results saved.", "saved": saved},
            status=status.HTTP_200_OK,
        )
