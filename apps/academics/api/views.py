from __future__ import annotations

from django.db import transaction
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework import status

from apps.common.tenant import get_tenant_context
from apps.common.permissions import IsBranchAdmin, IsTeacher, IsStudentOrParent
from apps.accounts.models import Role
from apps.academics.models import Batch, StudentProfile, TeacherProfile, BatchEnrollment, EnrollmentStatus, Subject, TimeTableSlot

from apps.academics.api.serializers import (
    BatchSerializer,
    StudentSerializer,
    StudentCreateSerializer,
    TeacherSerializer,
    TeacherCreateSerializer,
    EnrollmentSerializer,
    SubjectSerializer,
    TimeTableSlotSerializer,
)


class BatchViewSet(ModelViewSet):
    serializer_class = BatchSerializer
    permission_classes = [IsBranchAdmin]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return Batch.objects.filter(organisation=ctx.organisation, branch=ctx.branch).order_by("-created_at")

    def perform_create(self, serializer):
        ctx = get_tenant_context(self.request)
        serializer.save(organisation=ctx.organisation, branch=ctx.branch)


class TeacherViewSet(ModelViewSet):
    permission_classes = [IsBranchAdmin]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return TeacherProfile.objects.select_related("user").filter(
            organisation=ctx.organisation, branch=ctx.branch
        ).order_by("-created_at")

    def get_serializer_class(self):
        if self.action in {"create"}:
            return TeacherCreateSerializer
        return TeacherSerializer

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        teacher = s.save()
        out = TeacherSerializer(teacher).data
        return Response(out, status=status.HTTP_201_CREATED)


class StudentViewSet(ModelViewSet):
    permission_classes = [IsBranchAdmin]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return StudentProfile.objects.select_related("user").filter(
            organisation=ctx.organisation, branch=ctx.branch
        ).order_by("-created_at")

    def get_serializer_class(self):
        if self.action in {"create"}:
            return StudentCreateSerializer
        return StudentSerializer

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        student = s.save()
        out = StudentSerializer(student).data
        return Response(out, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], permission_classes=[IsBranchAdmin], url_path="enrollments")
    def enrollments(self, request, pk=None):
        ctx = get_tenant_context(request)
        student = self.get_object()
        qs = BatchEnrollment.objects.select_related("batch").filter(
            student=student, batch__branch=ctx.branch, batch__organisation=ctx.organisation
        ).order_by("-created_at")
        return Response(EnrollmentSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], permission_classes=[IsBranchAdmin], url_path="enroll")
    @transaction.atomic
    def enroll(self, request, pk=None):
        ctx = get_tenant_context(request)
        student = self.get_object()
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response({"batch_id": "Required."}, status=status.HTTP_400_BAD_REQUEST)

        batch = Batch.objects.filter(id=batch_id, organisation=ctx.organisation, branch=ctx.branch).first()
        if not batch:
            return Response({"batch_id": "Invalid batch."}, status=status.HTTP_400_BAD_REQUEST)

        enr, _ = BatchEnrollment.objects.update_or_create(
            batch=batch,
            student=student,
            defaults={"status": EnrollmentStatus.ACTIVE},
        )
        return Response(EnrollmentSerializer(enr).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsBranchAdmin], url_path="unenroll")
    @transaction.atomic
    def unenroll(self, request, pk=None):
        ctx = get_tenant_context(request)
        student = self.get_object()
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response({"batch_id": "Required."}, status=status.HTTP_400_BAD_REQUEST)

        enr = BatchEnrollment.objects.select_related("batch").filter(
            student=student,
            batch_id=batch_id,
            batch__organisation=ctx.organisation,
            batch__branch=ctx.branch,
        ).first()
        if not enr:
            return Response({"detail": "Enrollment not found."}, status=status.HTTP_404_NOT_FOUND)

        enr.status = EnrollmentStatus.LEFT
        enr.save(update_fields=["status", "updated_at"])
        return Response({"message": "Unenrolled."}, status=status.HTTP_200_OK)


class SubjectViewSet(ModelViewSet):
    serializer_class = SubjectSerializer
    permission_classes = [IsBranchAdmin]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return Subject.objects.filter(organisation=ctx.organisation, branch=ctx.branch).order_by("name")

    def perform_create(self, serializer):
        ctx = get_tenant_context(self.request)
        serializer.save(organisation=ctx.organisation, branch=ctx.branch)


class TimeTableSlotViewSet(ModelViewSet):
    serializer_class = TimeTableSlotSerializer
    permission_classes = [IsBranchAdmin]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return TimeTableSlot.objects.select_related("batch", "subject", "teacher").filter(
            organisation=ctx.organisation, branch=ctx.branch
        ).order_by("weekday", "start_time")

    def perform_create(self, serializer):
        ctx = get_tenant_context(self.request)
        serializer.save(organisation=ctx.organisation, branch=ctx.branch)