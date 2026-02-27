"""
attendance/api/views_reports.py  — COMPLETE FIXED VERSION

Bugs fixed vs original:
  1. enrolled_students query used wrong related_name: batchenrollment__batch
     The correct related_name is "enrollments" (from BatchEnrollment.student FK).
     Fixed to: enrollments__batch  (and enrollments__status)
"""
from __future__ import annotations

from django.db.models import Count, Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.mixins import TenantMixin
from apps.common.permissions import IsBranchAdmin
from apps.common.tenant import get_tenant_context
from apps.attendance.models import ClassSession, StudentAttendance, AttendanceStatus
from apps.academics.models import Batch, StudentProfile, BatchEnrollment, EnrollmentStatus


class AttendanceReportView(TenantMixin, APIView):
    """
    GET /api/attendance/report/

    Per-batch attendance aggregation for a date range.

    Query params:
        from_date  YYYY-MM-DD  required
        to_date    YYYY-MM-DD  required
        batch_id   int         optional

    Response:
    [
      {
        "batch_id": 1,
        "batch_name": "Xth Science",
        "total_sessions": 20,
        "total_students": 45,
        "avg_attendance_pct": 87.5,
        "present_count": 787,
        "absent_count": 113
      }
    ]
    """
    permission_classes = [IsBranchAdmin]

    def get(self, request):
        ctx       = get_tenant_context(request)
        from_date = request.query_params.get("from_date")
        to_date   = request.query_params.get("to_date")
        batch_id  = request.query_params.get("batch_id")

        if not from_date or not to_date:
            return Response(
                {"detail": "from_date and to_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sessions_qs = ClassSession.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
            session_date__gte=from_date,
            session_date__lte=to_date,
        )
        if batch_id:
            sessions_qs = sessions_qs.filter(batch_id=batch_id)

        batch_ids  = sessions_qs.values_list("batch_id", flat=True).distinct()
        batches    = Batch.objects.filter(id__in=batch_ids).only("id", "name")
        batch_map  = {b.id: b.name for b in batches}

        session_counts = (
            sessions_qs
            .values("batch_id")
            .annotate(total=Count("id"))
        )
        session_count_map = {r["batch_id"]: r["total"] for r in session_counts}

        att_qs = StudentAttendance.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
            session__session_date__gte=from_date,
            session__session_date__lte=to_date,
        )
        if batch_id:
            att_qs = att_qs.filter(batch_id=batch_id)

        att_agg = (
            att_qs
            .values("batch_id")
            .annotate(
                present=Count("id", filter=Q(status=AttendanceStatus.PRESENT)),
                absent=Count("id",  filter=Q(status=AttendanceStatus.ABSENT)),
                total=Count("id"),
            )
        )
        att_map = {r["batch_id"]: r for r in att_agg}

        # FIX: correct related_name is "enrollments" (not "batchenrollment__batch")
        enrollment_qs = (
            BatchEnrollment.objects
            .filter(
                batch__organisation=ctx.organisation,
                batch__branch=ctx.branch,
                status=EnrollmentStatus.ACTIVE,
            )
            .values("batch_id")
            .annotate(students=Count("id"))
        )
        if batch_id:
            enrollment_qs = enrollment_qs.filter(batch_id=batch_id)
        enrollment_map = {r["batch_id"]: r["students"] for r in enrollment_qs}

        result = []
        for bid in batch_map:
            att        = att_map.get(bid, {})
            present    = att.get("present", 0)
            total_att  = att.get("total", 0)
            avg_pct    = round(present / total_att * 100, 1) if total_att > 0 else 0.0

            result.append({
                "batch_id":           bid,
                "batch_name":         batch_map[bid],
                "total_sessions":     session_count_map.get(bid, 0),
                "total_students":     enrollment_map.get(bid, 0),
                "avg_attendance_pct": avg_pct,
                "present_count":      present,
                "absent_count":       att.get("absent", 0),
            })

        result.sort(key=lambda x: x["avg_attendance_pct"], reverse=True)
        return Response(result, status=status.HTTP_200_OK)


class StudentAttendanceSummaryView(TenantMixin, APIView):
    """
    GET /api/attendance/student-summary/

    Per-student attendance percentage for a batch over a date range.

    Query params:
        from_date  YYYY-MM-DD  required
        to_date    YYYY-MM-DD  required
        batch_id   int         required

    Response:
    {
      "batch_id": 1,
      "batch_name": "Xth Science",
      "from_date": "2026-01-01",
      "to_date": "2026-01-31",
      "total_sessions": 20,
      "students": [
        {
          "public_id": "STU-26-0000001",
          "name": "Rahul Kumar",
          "present": 18, "absent": 1, "late": 1,
          "attendance_pct": 90.0,
          "status": "Good"   // Good ≥80%, Warning 60-79%, Critical <60%
        }
      ]
    }
    """
    permission_classes = [IsBranchAdmin]

    def get(self, request):
        ctx       = get_tenant_context(request)
        from_date = request.query_params.get("from_date")
        to_date   = request.query_params.get("to_date")
        batch_id  = request.query_params.get("batch_id")

        if not from_date or not to_date or not batch_id:
            return Response(
                {"detail": "from_date, to_date, and batch_id are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch = Batch.objects.filter(
            id=batch_id,
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).first()
        if not batch:
            return Response({"detail": "Invalid batch."}, status=status.HTTP_400_BAD_REQUEST)

        total_sessions = ClassSession.objects.filter(
            batch=batch,
            session_date__gte=from_date,
            session_date__lte=to_date,
        ).count()

        att_agg = (
            StudentAttendance.objects
            .filter(
                batch=batch,
                session__session_date__gte=from_date,
                session__session_date__lte=to_date,
            )
            .values("student_id")
            .annotate(
                present=Count("id", filter=Q(status=AttendanceStatus.PRESENT)),
                absent=Count("id",  filter=Q(status=AttendanceStatus.ABSENT)),
                late=Count("id",    filter=Q(status=AttendanceStatus.LATE)),
            )
        )
        att_map = {r["student_id"]: r for r in att_agg}

        # FIX: Use correct related lookup (enrollments, not batchenrollment)
        enrolled_students = (
            StudentProfile.objects
            .filter(
                enrollments__batch=batch,        # FIX: was batchenrollment__batch
                enrollments__status=EnrollmentStatus.ACTIVE,  # FIX: was batchenrollment__status
            )
            .select_related("user")
            .distinct()
        )

        students_data = []
        for student in enrolled_students:
            att     = att_map.get(student.id, {"present": 0, "absent": 0, "late": 0})
            present = att["present"]
            pct     = round(present / total_sessions * 100, 1) if total_sessions > 0 else 0.0
            att_status = "Good" if pct >= 80 else ("Warning" if pct >= 60 else "Critical")

            students_data.append({
                "public_id":      student.public_id,
                "name":           student.user.full_name or student.user.mobile,
                "present":        present,
                "absent":         att["absent"],
                "late":           att["late"],
                "attendance_pct": pct,
                "status":         att_status,
            })

        students_data.sort(key=lambda x: x["attendance_pct"])

        return Response(
            {
                "batch_id":       int(batch_id),
                "batch_name":     batch.name,
                "from_date":      from_date,
                "to_date":        to_date,
                "total_sessions": total_sessions,
                "students":       students_data,
            },
            status=status.HTTP_200_OK,
        )
