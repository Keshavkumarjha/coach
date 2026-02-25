from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework import status

from apps.common.tenant import get_tenant_context
from apps.common.permissions import IsBranchAdmin, IsTeacher
from apps.accounts.models import Role
from apps.attendance.models import ClassSession, StudentAttendance, AttendanceStatus, MarkedBy
from apps.academics.models import Batch, StudentProfile

from apps.attendance.api.serializers import (
    ClassSessionSerializer,
    TeacherBulkMarkSerializer,
    StudentGeoMarkSerializer,
    )


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        ctx = get_tenant_context(request)
        return ctx.membership.role == Role.STUDENT


class ClassSessionViewSet(ModelViewSet):
    serializer_class = ClassSessionSerializer
    permission_classes = [IsTeacher]  # teacher can create sessions

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return ClassSession.objects.filter(
            organisation=ctx.organisation, branch=ctx.branch
        ).select_related("batch").order_by("-session_date", "-created_at")

    def perform_create(self, serializer):
        ctx = get_tenant_context(self.request)
        batch_id = self.request.data.get("batch_id")
        if not batch_id:
            raise ValueError("batch_id required")

        batch = Batch.objects.filter(id=batch_id, organisation=ctx.organisation, branch=ctx.branch).first()
        if not batch:
            raise ValueError("Invalid batch_id")

        serializer.save(
            organisation=ctx.organisation,
            branch=ctx.branch,
            batch=batch,
            created_by=self.request.user,
            session_date=serializer.validated_data.get("session_date") or timezone.localdate(),
        )

    @action(detail=True, methods=["post"], permission_classes=[IsTeacher], url_path="close")
    def close(self, request, pk=None):
        session = self.get_object()
        session.status = "CLOSED"
        session.save(update_fields=["status", "updated_at"])
        return Response({"message": "Session closed."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsTeacher], url_path="open")
    def open_session(self, request, pk=None):
        session = self.get_object()
        session.status = "OPEN"
        session.save(update_fields=["status", "updated_at"])
        return Response({"message": "Session opened."}, status=status.HTTP_200_OK)


class StudentAttendanceViewSet(ModelViewSet):
    """
    Admin/Teacher can list records. Marking is via custom actions:
      - /attendance/teacher-bulk-mark/
      - /attendance/student-geo-mark/
    """
    serializer_class = None  # listing handled by minimal dict response
    permission_classes = [IsTeacher]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return StudentAttendance.objects.filter(
            organisation=ctx.organisation, branch=ctx.branch
        ).select_related("session", "student").order_by("-marked_at")

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()[:200]  # protect huge responses
        data = [
            {
                "id": a.id,
                "session_id": a.session_id,
                "student_public_id": a.student.public_id,
                "status": a.status,
                "marked_by_type": a.marked_by_type,
                "marked_at": a.marked_at,
            }
            for a in qs
        ]
        return Response(data)

    @action(detail=False, methods=["post"], permission_classes=[IsTeacher], url_path="teacher-bulk-mark")
    @transaction.atomic
    def teacher_bulk_mark(self, request):
        ctx = get_tenant_context(request)
        s = TeacherBulkMarkSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        session_id = s.validated_data["session_id"]
        session = ClassSession.objects.filter(
            id=session_id, organisation=ctx.organisation, branch=ctx.branch
        ).select_related("batch").first()
        if not session:
            return Response({"session_id": "Invalid session."}, status=status.HTTP_400_BAD_REQUEST)

        # Map public_id -> StudentProfile
        public_ids = [r["student_public_id"] for r in s.validated_data["records"]]
        students = {
            st.public_id: st
            for st in StudentProfile.objects.filter(
                organisation=ctx.organisation, branch=ctx.branch, public_id__in=public_ids
            )
        }

        upserts = 0
        for r in s.validated_data["records"]:
            st = students.get(r["student_public_id"])
            if not st:
                continue
            StudentAttendance.objects.update_or_create(
                session=session,
                student=st,
                defaults={
                    "organisation": ctx.organisation,
                    "branch": ctx.branch,
                    "batch": session.batch,
                    "status": r["status"],
                    "marked_by_type": MarkedBy.TEACHER,
                    "marked_by_user": request.user,
                    "marked_at": timezone.now(),
                },
            )
            upserts += 1

        return Response({"message": "Attendance saved.", "updated": upserts}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], permission_classes=[IsStudent], url_path="student-geo-mark")
    @transaction.atomic
    def student_geo_mark(self, request):
        ctx = get_tenant_context(request)
        s = StudentGeoMarkSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)

        session = s.validated_data["_session"]
        student = s.validated_data["_student"]
        distance_m = s.validated_data["_distance_m"]

        att, _ = StudentAttendance.objects.update_or_create(
            session=session,
            student=student,
            defaults={
                "organisation": ctx.organisation,
                "branch": ctx.branch,
                "batch": session.batch,
                "status": s.validated_data["status"],
                "marked_by_type": MarkedBy.STUDENT_GEO,
                "marked_by_user": request.user,
                "marked_at": timezone.now(),
                "distance_from_branch_m": distance_m,
                # If you use non-PostGIS:
                "marked_lat": s.validated_data["lat"],
                "marked_lng": s.validated_data["lng"],
            },
        )

        return Response(
            {
                "message": "Attendance marked.",
                "status": att.status,
                "distance_m": distance_m,
            },
            status=status.HTTP_200_OK,
        )