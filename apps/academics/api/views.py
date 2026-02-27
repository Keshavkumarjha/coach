"""
academics/api/views.py  — COMPLETE FIXED VERSION

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
  — Students see only their enrolled batches' slots (FIX #1)
"""
from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet, SearchFilterMixin, StatusFilterMixin
from apps.common.permissions import IsBranchAdmin, IsStudentOrParent
from apps.academics.models import (
    Batch,
    BatchEnrollment,
    EnrollmentStatus,
    StudentProfile,
    Subject,
    TeacherProfile,
    TimeTableSlot,
)
from apps.academics.api.serializers import (
    BatchSerializer,
    EnrollmentSerializer,
    StudentCreateSerializer,
    StudentSerializer,
    SubjectSerializer,
    TeacherCreateSerializer,
    TeacherSerializer,
    TimeTableSlotSerializer,
)


class BatchViewSet(StatusFilterMixin, TenantViewSet):
    """
    CRUD for Batches scoped to current branch.
    Query params: ?status=ACTIVE | COMPLETED | UPCOMING
    """
    serializer_class = BatchSerializer
    permission_classes = [IsBranchAdmin]
    queryset = Batch.objects.prefetch_related("schedule_days").all()
    ordering = ["-created_at"]


class SubjectViewSet(SearchFilterMixin, TenantViewSet):
    """
    CRUD for Subjects scoped to current branch.
    Query params: ?search=<name>
    """
    serializer_class = SubjectSerializer
    permission_classes = [IsBranchAdmin]
    queryset = Subject.objects.all()
    ordering = ["name"]
    search_fields = ["name__icontains"]


class TeacherViewSet(SearchFilterMixin, TenantViewSet):
    """
    CRUD for TeacherProfiles scoped to current branch.
    Query params: ?search=<name or mobile>
    """
    queryset = TeacherProfile.objects.select_related("user").all()
    ordering = ["-created_at"]
    permission_classes = [IsBranchAdmin]
    search_fields = ["user__full_name__icontains", "user__mobile__icontains"]

    def get_serializer_class(self):
        if self.action == "create":
            return TeacherCreateSerializer
        return TeacherSerializer


class StudentViewSet(SearchFilterMixin, TenantViewSet):
    """
    CRUD for StudentProfiles scoped to current branch.
    Query params: ?search=<name, mobile, or admission_no>

    Custom actions:
        GET  /{id}/enrollments/   List batch enrollments for this student
        POST /{id}/enroll/        Enroll into a batch  { batch_id }
        POST /{id}/unenroll/      Mark enrollment as LEFT  { batch_id }
    """
    queryset = StudentProfile.objects.select_related("user").all()
    ordering = ["-created_at"]
    permission_classes = [IsBranchAdmin]
    search_fields = [
        "user__full_name__icontains",
        "user__mobile__icontains",
        "admission_no__icontains",
    ]

    def get_serializer_class(self):
        if self.action == "create":
            return StudentCreateSerializer
        return StudentSerializer

    @action(detail=True, methods=["get"], url_path="enrollments")
    def enrollments(self, request, pk=None):
        """GET /api/students/{id}/enrollments/"""
        student = self.get_object()
        qs = (
            BatchEnrollment.objects
            .select_related("batch")
            .filter(student=student)
            .order_by("-created_at")
        )
        return Response(EnrollmentSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="enroll")
    @transaction.atomic
    def enroll(self, request, pk=None):
        """
        POST /api/students/{id}/enroll/
        Body: { "batch_id": <int> }
        Creates or re-activates a BatchEnrollment.
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


# ═══════════════════════════════════════════════════════════════════════════════
# FIX #1 — TimeTableSlotViewSet: role-aware queryset
#
# PROBLEM: All roles (student, parent, teacher, admin) received every
#          timetable slot in the branch. Students saw other batches' schedules.
#
# FIX:     When the requesting user is STUDENT or PARENT, filter the queryset
#          to only include slots from batches the student is actively enrolled in.
#          Admins and teachers still see everything.
# ═══════════════════════════════════════════════════════════════════════════════
class TimeTableSlotViewSet(TenantViewSet):
    """
    CRUD for TimeTableSlots scoped to current branch.

    Permissions:
        create / update / delete  → IsBranchAdmin
        list / retrieve           → IsStudentOrParent  OR  IsBranchAdmin

    Query params:
        ?batch_id=<int>    Filter by batch (admin/teacher; auto-applied for students)
        ?weekday=<0-6>     0=Monday … 6=Sunday

    Role-aware queryset:
        STUDENT / PARENT  → Only their enrolled batches' slots
        TEACHER / ADMIN   → All slots in the branch
    """
    serializer_class = TimeTableSlotSerializer
    queryset = TimeTableSlot.objects.select_related("batch", "subject", "teacher").all()
    ordering = ["weekday", "start_time"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsBranchAdmin()]
        return [IsStudentOrParent()]

    def get_queryset(self):
        from apps.accounts.models import Role

        qs = super().get_queryset()
        ctx = self.get_tenant()
        role = ctx.membership.role

        # ── Student / Parent: restrict to enrolled batches ────────────────────
        if role in {Role.STUDENT, Role.PARENT}:
            student = (
                StudentProfile.objects
                .filter(
                    user=self.request.user,
                    organisation=ctx.organisation,
                    branch=ctx.branch,
                )
                .first()
            )
            if not student:
                return qs.none()

            enrolled_batch_ids = (
                BatchEnrollment.objects
                .filter(student=student, status=EnrollmentStatus.ACTIVE)
                .values_list("batch_id", flat=True)
            )
            qs = qs.filter(batch_id__in=enrolled_batch_ids)

        # ── Optional manual filters (admin/teacher) ───────────────────────────
        batch_id = self.request.query_params.get("batch_id")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)

        weekday = self.request.query_params.get("weekday")
        if weekday is not None:
            qs = qs.filter(weekday=weekday)

        return qs
