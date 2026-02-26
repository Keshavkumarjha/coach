"""
attendance/api/views.py

Class sessions and student attendance management.

Endpoints
─────────
Sessions (Teacher)
  GET/POST       /api/sessions/
  GET/PATCH/DEL  /api/sessions/{id}/
  POST           /api/sessions/{id}/open/
  POST           /api/sessions/{id}/close/

Attendance
  GET            /api/attendance/                    List records (admin/teacher)
  POST           /api/attendance/teacher-bulk-mark/  Bulk mark by teacher
  POST           /api/attendance/student-geo-mark/   Self-mark with GPS (student)
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
        to_date = self.request.query_params.get("to_date")
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
            session_date=serializer.validated_data.get("session_date") or timezone.localdate(),
        )

    def _set_status(self, request, session_status: str):
        session = self.get_object()
        session.status = session_status
        session.save(update_fields=["status", "updated_at"])
        return Response(
            {"message": f"Session {session_status.lower()}."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="open")
    def open_session(self, request, pk=None):
        """POST /api/sessions/{id}/open/ — re-open a closed session."""
        return self._set_status(request, "OPEN")

    @action(detail=True, methods=["post"], url_path="close")
    def close_session(self, request, pk=None):
        """POST /api/sessions/{id}/close/ — close an open session."""
        return self._set_status(request, "CLOSED")


class StudentAttendanceViewSet(BatchFilterMixin, DateRangeFilterMixin, TenantViewSet):
    """
    Read attendance records (admin/teacher) and mark attendance (teacher or student).

    GET  /api/attendance/                    List records (paginated)
    POST /api/attendance/teacher-bulk-mark/  Teacher marks whole session at once
    POST /api/attendance/student-geo-mark/   Student self-marks with GPS coordinates

    Query params (list):
        ?batch_id=<int>
        ?from_date=YYYY-MM-DD
        ?to_date=YYYY-MM-DD

    teacher-bulk-mark payload:
        {
          "session_id": 12,
          "records": [
            {"student_public_id": "STU-26-0000001", "status": "PRESENT"},
            {"student_public_id": "STU-26-0000002", "status": "ABSENT"}
          ]
        }

    student-geo-mark payload:
        { "session_id": 12, "lat": 28.6139, "lng": 77.2090 }
    """
    serializer_class = ClassSessionSerializer  # not used for list; overridden below
    permission_classes = [IsTeacher]
    queryset = StudentAttendance.objects.select_related("session", "student", "student__user").all()
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
                "id": a.id,
                "session_id": a.session_id,
                "student_public_id": a.student.public_id,
                "student_name": a.student.user.full_name,
                "status": a.status,
                "marked_by_type": a.marked_by_type,
                "marked_at": a.marked_at,
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
                    "organisation": ctx.organisation,
                    "branch": ctx.branch,
                    "batch": session.batch,
                    "status": record["status"],
                    "marked_by_type": MarkedBy.TEACHER,
                    "marked_by_user": request.user,
                    "marked_at": timezone.now(),
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
        Student self-marks with GPS. Validates distance from branch geo center.
        """
        ctx = self.get_tenant()
        serializer = StudentGeoMarkSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        session = serializer.validated_data["_session"]
        student = serializer.validated_data["_student"]
        distance_m = serializer.validated_data["_distance_m"]

        attendance, _ = StudentAttendance.objects.update_or_create(
            session=session,
            student=student,
            defaults={
                "organisation": ctx.organisation,
                "branch": ctx.branch,
                "batch": session.batch,
                "status": serializer.validated_data["status"],
                "marked_by_type": MarkedBy.STUDENT_GEO,
                "marked_by_user": request.user,
                "marked_at": timezone.now(),
                "distance_from_branch_m": distance_m,
                "marked_lat": serializer.validated_data["lat"],
                "marked_lng": serializer.validated_data["lng"],
            },
        )

        return Response(
            {
                "message": "Attendance marked.",
                "status": attendance.status,
                "distance_m": distance_m,
            },
            status=status.HTTP_200_OK,
        )
