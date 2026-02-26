"""
academics/api/views.py

All academic resource ViewSets.

Endpoints
─────────
Batches
  GET/POST        /api/batches/
  GET/PATCH/DEL   /api/batches/{id}/

Subjects
  GET/POST        /api/subjects/
  GET/PATCH/DEL   /api/subjects/{id}/

Teachers
  GET/POST        /api/teachers/
  GET/PATCH/DEL   /api/teachers/{id}/

Students
  GET/POST        /api/students/
  GET/PATCH/DEL   /api/students/{id}/
  GET             /api/students/{id}/enrollments/
  POST            /api/students/{id}/enroll/
  POST            /api/students/{id}/unenroll/

Timetable
  GET/POST        /api/timetable/
  GET/PATCH/DEL   /api/timetable/{id}/
"""
from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet, SearchFilterMixin, StatusFilterMixin
from apps.common.permissions import IsBranchAdmin
from apps.academics.models import (
    Batch,
    StudentProfile,
    TeacherProfile,
    BatchEnrollment,
    EnrollmentStatus,
    Subject,
    TimeTableSlot,
)
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


class BatchViewSet(StatusFilterMixin, TenantViewSet):
    """
    CRUD for Batches scoped to the current branch.

    Query params:
        ?status=ACTIVE | ARCHIVED
        ?search=<name or code>
    """
    serializer_class = BatchSerializer
    permission_classes = [IsBranchAdmin]
    queryset = Batch.objects.all()
    ordering = ["-created_at"]
    search_fields = ["name__icontains", "code__icontains"]

    def get_queryset(self):
        ctx = self.get_tenant()
        return Batch.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).prefetch_related("schedule_days").order_by(*self.ordering)


class SubjectViewSet(SearchFilterMixin, TenantViewSet):
    """
    CRUD for Subjects scoped to the current branch.

    Query params:
        ?search=<name>
    """
    serializer_class = SubjectSerializer
    permission_classes = [IsBranchAdmin]
    queryset = Subject.objects.all()
    ordering = ["name"]
    search_fields = ["name__icontains"]


class TeacherViewSet(SearchFilterMixin, TenantViewSet):
    """
    CRUD for TeacherProfiles.

    Create uses TeacherCreateSerializer (handles User creation + OrgMembership).
    List/Retrieve/Update uses TeacherSerializer.

    Query params:
        ?search=<name, mobile, employee_id>
    """
    permission_classes = [IsBranchAdmin]
    queryset = TeacherProfile.objects.select_related("user").all()
    ordering = ["-created_at"]
    search_fields = [
        "user__full_name__icontains",
        "user__mobile__icontains",
        "employee_id__icontains",
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return TeacherCreateSerializer
        return TeacherSerializer

    def create(self, request, *args, **kwargs):
        serializer = TeacherCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        teacher = serializer.save()
        return Response(
            TeacherSerializer(teacher).data,
            status=status.HTTP_201_CREATED,
        )


class StudentViewSet(SearchFilterMixin, TenantViewSet):
    """
    CRUD for StudentProfiles.

    Create uses StudentCreateSerializer (handles User + optional enrollment).
    List/Retrieve/Update uses StudentSerializer.

    Query params:
        ?search=<name, mobile, admission_no>

    Custom actions:
        GET  /{id}/enrollments/   List all batch enrollments
        POST /{id}/enroll/        Enroll into a batch  { "batch_id": <int> }
        POST /{id}/unenroll/      Unenroll from batch  { "batch_id": <int> }
    """
    permission_classes = [IsBranchAdmin]
    queryset = StudentProfile.objects.select_related("user").all()
    ordering = ["-created_at"]
    search_fields = [
        "user__full_name__icontains",
        "user__mobile__icontains",
        "admission_no__icontains",
        "roll_no__icontains",
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return StudentCreateSerializer
        return StudentSerializer

    def create(self, request, *args, **kwargs):
        serializer = StudentCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        student = serializer.save()
        return Response(
            StudentSerializer(student).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="enrollments")
    def enrollments(self, request, pk=None):
        """
        GET /api/students/{id}/enrollments/
        Returns all batch enrollments for this student.
        """
        ctx = self.get_tenant()
        student = self.get_object()
        qs = (
            BatchEnrollment.objects
            .select_related("batch")
            .filter(
                student=student,
                batch__branch=ctx.branch,
                batch__organisation=ctx.organisation,
            )
            .order_by("-created_at")
        )
        return Response(EnrollmentSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="enroll")
    @transaction.atomic
    def enroll(self, request, pk=None):
        """
        POST /api/students/{id}/enroll/
        Body: { "batch_id": <int> }
        Enrolls the student into the given batch (upsert: reactivates if LEFT).
        """
        ctx = self.get_tenant()
        student = self.get_object()
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response(
                {"batch_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        batch = Batch.objects.filter(
            id=batch_id,
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).first()
        if not batch:
            return Response(
                {"batch_id": "Invalid batch for this branch."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        enrollment, _ = BatchEnrollment.objects.update_or_create(
            batch=batch,
            student=student,
            defaults={"status": EnrollmentStatus.ACTIVE},
        )
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="unenroll")
    @transaction.atomic
    def unenroll(self, request, pk=None):
        """
        POST /api/students/{id}/unenroll/
        Body: { "batch_id": <int> }
        Marks the enrollment as LEFT.
        """
        ctx = self.get_tenant()
        student = self.get_object()
        batch_id = request.data.get("batch_id")
        if not batch_id:
            return Response(
                {"batch_id": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        enrollment = (
            BatchEnrollment.objects
            .select_related("batch")
            .filter(
                student=student,
                batch_id=batch_id,
                batch__organisation=ctx.organisation,
                batch__branch=ctx.branch,
            )
            .first()
        )
        if not enrollment:
            return Response(
                {"detail": "Enrollment not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        enrollment.status = EnrollmentStatus.LEFT
        enrollment.save(update_fields=["status", "updated_at"])
        return Response({"message": "Student unenrolled."}, status=status.HTTP_200_OK)


class TimeTableSlotViewSet(TenantViewSet):
    """
    CRUD for TimeTableSlots scoped to current branch.

    Query params:
        ?batch_id=<int>   Filter by batch
    """
    serializer_class = TimeTableSlotSerializer
    permission_classes = [IsBranchAdmin]
    queryset = TimeTableSlot.objects.select_related("batch", "subject", "teacher").all()
    ordering = ["weekday", "start_time"]

    def get_queryset(self):
        qs = super().get_queryset()
        batch_id = self.request.query_params.get("batch_id")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        return qs
