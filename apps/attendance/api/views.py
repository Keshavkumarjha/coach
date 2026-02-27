"""
attendance/api/views.py  — COMPLETE FIXED VERSION

Class sessions and student attendance management.

Endpoints
─────────
Sessions (Teacher)
  GET/POST       /api/sessions/
  GET/PATCH/DEL  /api/sessions/{id}/
  POST           /api/sessions/{id}/open/
  POST           /api/sessions/{id}/close/

Attendance
  GET            /api/attendance/                      List records (admin/teacher)
  POST           /api/attendance/teacher-bulk-mark/    Bulk mark by teacher
  POST           /api/attendance/student-geo-mark/     Self-mark with GPS (student)
  PATCH          /api/attendance/{id}/correct/         Correct one record  ← FIX #8 (new)
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from apps.common.mixins import (
    TenantViewSet,
    BulkActionMixin,
    BatchFilterMixin,
    DateRangeFilterMixin,
    StandardPagination,
)
from apps.common.permissions import IsBranchAdmin, IsTeacher
from apps.common.tenant import get_tenant_context
from apps.accounts.models import Role
from apps.attendance.models import (
    ClassSession,
    StudentAttendance,
    AttendanceStatus,
    MarkedBy,
)
from apps.academics.models import Batch, StudentProfile
from apps.attendance.api.serializers import (
    ClassSessionSerializer,
    TeacherBulkMarkSerializer,
    StudentGeoMarkSerializer,
)


class IsStudent(BasePermission):
    """Allows access only to users with the STUDENT role in the current tenant."""
    def has_permission(self, request, view):
        ctx = get_tenant_context(request)
        return ctx.membership.role == Role.STUDENT


class ClassSessionViewSet(TenantViewSet):
    """
    Teacher-managed class sessions.

    Query params:
        ?batch_id=<int>
        ?from_date=YYYY-MM-DD
        ?to_date=YYYY-MM-DD
        ?status=OPEN | CLOSED | CANCELLED

    Custom actions:
        POST /{id}/open/    Re-open a session
        POST /{id}/close/   Close a session
    """
    serializer_class = ClassSessionSerializer
    permission_classes = [IsTeacher]
    queryset = ClassSession.objects.select_related("batch").all()
    ordering = ["-session_date", "-created_at"]
    inject_created_by = True

    def get_queryset(self):
        qs = super().get_queryset()
        batch_id = self.request.query_params.get("batch_id")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        session_status = self.request.query_params.get("status")
        if session_status:
            qs = qs.filter(status=session_status.upper())
        from_date = self.request.query_params.get("from_date")
        to_date   = self.request.query_params.get("to_date")
        if from_date:
            qs = qs.filter(session_date__gte=from_date)
        if to_date:
            qs = qs.filter(session_date__lte=to_date)
        return qs

    def perform_create(self, serializer):
        ctx = self.get_tenant()
        batch_id = self.request.data.get("batch_id")
        if not batch_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"batch_id": "This field is required."})
        batch = Batch.objects.filter(
            id=batch_id,
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).first()
        if not batch:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"batch_id": "Invalid batch for this branch."})
        serializer.save(
            organisation=ctx.organisation,
            branch=ctx.branch,
            batch=batch,
            created_by=self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="open")
    def open(self, request, pk=None):
        """POST /api/sessions/{id}/open/  — Re-open a closed session."""
        session = self.get_object()
        from apps.attendance.models import SessionStatus
        session.status = SessionStatus.OPEN
        session.save(update_fields=["status", "updated_at"])
        return Response({"message": "Session opened."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="close")
    def close(self, request, pk=None):
        """POST /api/sessions/{id}/close/  — Close an open session."""
        session = self.get_object()
        from apps.attendance.models import SessionStatus
        session.status = SessionStatus.CLOSED
        session.save(update_fields=["status", "updated_at"])
        return Response({"message": "Session closed."}, status=status.HTTP_200_OK)


class StudentAttendanceViewSet(BatchFilterMixin, DateRangeFilterMixin, TenantViewSet):
    """
    Read attendance records (admin/teacher) and mark attendance (teacher or student).

    GET  /api/attendance/                    List records (paginated)
    POST /api/attendance/teacher-bulk-mark/  Teacher marks whole session at once
    POST /api/attendance/student-geo-mark/   Student self-marks with GPS coordinates
    PATCH /api/attendance/{id}/correct/      Correct a single attendance record (NEW)

    Query params (list):
        ?batch_id=<int>
        ?from_date=YYYY-MM-DD
        ?to_date=YYYY-MM-DD
    """
    serializer_class = ClassSessionSerializer   # not used for list; overridden below
    permission_classes = [IsTeacher]
    queryset = StudentAttendance.objects.select_related(
        "session", "student", "student__user"
    ).all()
    ordering = ["-marked_at"]
    date_filter_field = "marked_at__date"

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        if page is not None:
            data = self._serialize_records(page)
            return self.get_paginated_response(data)
        return Response(self._serialize_records(qs))

    @staticmethod
    def _serialize_records(qs):
        return [
            {
                "id":               a.id,
                "session_id":       a.session_id,
                "student_public_id": a.student.public_id,
                "student_name":     a.student.user.full_name,
                "status":           a.status,
                "marked_by_type":   a.marked_by_type,
                "marked_at":        a.marked_at,
            }
            for a in qs
        ]

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsTeacher],
        url_path="teacher-bulk-mark",
    )
    @transaction.atomic
    def teacher_bulk_mark(self, request):
        """
        POST /api/attendance/teacher-bulk-mark/
        Teacher marks multiple students for a session in one call.

        Body:
            session_id  int   required
            records     list  required  [{ student_public_id, status }]
        """
        ctx = self.get_tenant()
        serializer = TeacherBulkMarkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = ClassSession.objects.filter(
            id=serializer.validated_data["session_id"],
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).select_related("batch").first()
        if not session:
            return Response(
                {"session_id": "Invalid session."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        public_ids = [r["student_public_id"] for r in serializer.validated_data["records"]]
        student_map = {
            st.public_id: st
            for st in StudentProfile.objects.filter(
                organisation=ctx.organisation,
                branch=ctx.branch,
                public_id__in=public_ids,
            )
        }

        saved = 0
        for record in serializer.validated_data["records"]:
            student = student_map.get(record["student_public_id"])
            if not student:
                continue
            StudentAttendance.objects.update_or_create(
                session=session,
                student=student,
                defaults={
                    "organisation":   ctx.organisation,
                    "branch":         ctx.branch,
                    "batch":          session.batch,
                    "status":         record["status"],
                    "marked_by_type": MarkedBy.TEACHER,
                    "marked_by_user": request.user,
                    "marked_at":      timezone.now(),
                },
            )
            saved += 1

        return Response(
            {"message": "Attendance saved.", "saved": saved},
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        permission_classes=[IsStudent],
        url_path="student-geo-mark",
    )
    @transaction.atomic
    def student_geo_mark(self, request):
        """
        POST /api/attendance/student-geo-mark/
        Student self-marks attendance for an open session using GPS coordinates.

        Body:
            session_id  int     required
            lat         float   required
            lng         float   required
            status      string  optional  default: PRESENT
        """
        ctx = get_tenant_context(request)
        serializer = StudentGeoMarkSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        session = vd["_session"]
        student = vd["_student"]

        attendance, created = StudentAttendance.objects.update_or_create(
            session=session,
            student=student,
            defaults={
                "organisation":   ctx.organisation,
                "branch":         ctx.branch,
                "batch":          session.batch,
                "status":         vd.get("status", AttendanceStatus.PRESENT),
                "marked_by_type": MarkedBy.STUDENT,
                "marked_by_user": request.user,
                "marked_at":      timezone.now(),
            },
        )
        return Response(
            {
                "message":     "Attendance marked.",
                "status":      attendance.status,
                "distance_m":  vd["_distance_m"],
            },
            status=status.HTTP_200_OK,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # FIX #8 — add PATCH /api/attendance/{id}/correct/
    #
    # PROBLEM: Once attendance was marked (by teacher or student self-mark),
    #          there was no endpoint to correct it. If a teacher accidentally
    #          marked a student ABSENT when they were PRESENT, the only option
    #          was direct DB access. The teacher-bulk-mark endpoint re-marks the
    #          whole session, but that requires knowing all students.
    #
    # FIX:     Added a `correct` @action (detail=True, PATCH).
    #          - Takes { "status": "PRESENT" | "ABSENT" | "LATE", "note": "..." }
    #          - Updates the single StudentAttendance record
    #          - Records the correction as marked_by_type=TEACHER and overwrites
    #            the original marked_by_user with the correcting teacher
    #          - Only IsTeacher can call this (no student self-correction)
    # ═══════════════════════════════════════════════════════════════════════════
    @action(
        detail=True,
        methods=["patch"],
        permission_classes=[IsTeacher],
        url_path="correct",
    )
    @transaction.atomic
    def correct(self, request, pk=None):
        """
        PATCH /api/attendance/{id}/correct/

        Corrects a single attendance record. Used when a teacher needs to change
        a student's status after bulk-marking (e.g., Absent → Present after the
        student provides a valid explanation).

        Body:
            status   string   required   PRESENT | ABSENT | LATE
            note     string   optional   Reason for correction (max 200 chars)

        Response:
            {
              "id":               42,
              "student_public_id": "STU-26-0000001",
              "student_name":     "Rahul Kumar",
              "session_id":       12,
              "old_status":       "ABSENT",
              "new_status":       "PRESENT",
              "corrected_by":     "teacher@email.com",
              "corrected_at":     "2026-02-27T10:30:00Z",
              "note":             "Student showed doctor's certificate"
            }
        """
        from rest_framework import serializers as drf_serializers

        # ── Validate input ────────────────────────────────────────────────────
        new_status = (request.data.get("status") or "").strip().upper()
        note       = (request.data.get("note") or "").strip()[:200]

        if new_status not in AttendanceStatus.values:
            return Response(
                {
                    "status": (
                        f"Invalid status '{new_status}'. "
                        f"Valid choices: {', '.join(AttendanceStatus.values)}"
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        attendance = self.get_object()
        old_status = attendance.status

        # ── Apply correction ──────────────────────────────────────────────────
        attendance.status         = new_status
        attendance.marked_by_type = MarkedBy.TEACHER
        attendance.marked_by_user = request.user
        attendance.marked_at      = timezone.now()
        attendance.save(
            update_fields=[
                "status",
                "marked_by_type",
                "marked_by_user",
                "marked_at",
                "updated_at",
            ]
        )

        return Response(
            {
                "id":                attendance.id,
                "student_public_id": attendance.student.public_id,
                "student_name":      attendance.student.user.full_name,
                "session_id":        attendance.session_id,
                "old_status":        old_status,
                "new_status":        attendance.status,
                "corrected_by":      request.user.mobile or str(request.user),
                "corrected_at":      attendance.marked_at,
                "note":              note,
            },
            status=status.HTTP_200_OK,
        )
