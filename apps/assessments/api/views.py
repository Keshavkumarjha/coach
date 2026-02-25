from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.tenant import get_tenant_context
from apps.common.permissions import IsBranchAdmin, IsTeacher, IsStudentOrParent
from apps.accounts.models import Role
from apps.assessments.models import StudyMaterial, Homework, HomeworkSubmission, Test, StudentTestResult
from apps.academics.models import StudentProfile

from apps.assessments.api.serializers import (
    StudyMaterialSerializer,
    HomeworkSerializer,
    HomeworkSubmissionCreateSerializer,
    HomeworkSubmissionSerializer,
    TestSerializer,
    StudentTestResultUpsertSerializer,
    StudentTestResultSerializer,
)


class StudyMaterialViewSet(ModelViewSet):
    serializer_class = StudyMaterialSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTeacher()]
        return [IsStudentOrParent()]  # students/parents can view

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return StudyMaterial.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(request=self.request)


class HomeworkViewSet(ModelViewSet):
    serializer_class = HomeworkSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsTeacher()]
        return [IsStudentOrParent()]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return Homework.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(request=self.request)

    @action(detail=True, methods=["get"], permission_classes=[IsTeacher], url_path="submissions")
    def submissions(self, request, pk=None):
        ctx = get_tenant_context(request)
        hw = self.get_object()
        qs = HomeworkSubmission.objects.select_related("student", "student__user").filter(homework=hw).order_by("-created_at")
        return Response(HomeworkSubmissionSerializer(qs, many=True).data)

    @action(detail=False, methods=["post"], permission_classes=[IsStudentOrParent], url_path="submit")
    @transaction.atomic
    def submit(self, request):
        s = HomeworkSubmissionCreateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        sub = s.save()
        return Response(HomeworkSubmissionSerializer(sub).data, status=status.HTTP_201_CREATED)


class TestViewSet(ModelViewSet):
    serializer_class = TestSerializer

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy", "upsert_results"}:
            return [IsTeacher()]
        return [IsStudentOrParent()]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return Test.objects.filter(organisation=ctx.organisation, branch=ctx.branch).order_by("-scheduled_on", "-created_at")

    def perform_create(self, serializer):
        serializer.save(request=self.request)

    @action(detail=True, methods=["get"], permission_classes=[IsStudentOrParent], url_path="results")
    def my_results(self, request, pk=None):
        ctx = get_tenant_context(request)
        student = getattr(request.user, "student_profile", None)
        if not student:
            return Response({"detail": "Student login required."}, status=status.HTTP_400_BAD_REQUEST)

        test = self.get_object()
        res = StudentTestResult.objects.filter(test=test, student=student).first()
        return Response(StudentTestResultSerializer(res).data if res else {}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], permission_classes=[IsTeacher], url_path="upsert-results")
    @transaction.atomic
    def upsert_results(self, request):
        ctx = get_tenant_context(request)
        s = StudentTestResultUpsertSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        test = Test.objects.filter(id=s.validated_data["test_id"], organisation=ctx.organisation, branch=ctx.branch).first()
        if not test:
            return Response({"test_id": "Invalid test."}, status=status.HTTP_400_BAD_REQUEST)

        public_ids = [r["student_public_id"] for r in s.validated_data["results"]]
        students = {
            st.public_id: st
            for st in StudentProfile.objects.filter(organisation=ctx.organisation, branch=ctx.branch, public_id__in=public_ids)
        }

        updated = 0
        for r in s.validated_data["results"]:
            st = students.get(r["student_public_id"])
            if not st:
                continue
            StudentTestResult.objects.update_or_create(
                test=test,
                student=st,
                defaults={
                    "marks_obtained": r.get("marks_obtained", 0),
                    "grade": r.get("grade", ""),
                    "remarks": r.get("remarks", ""),
                    "entered_by": request.user,
                },
            )
            updated += 1

        return Response({"message": "Results saved.", "updated": updated}, status=status.HTTP_200_OK)