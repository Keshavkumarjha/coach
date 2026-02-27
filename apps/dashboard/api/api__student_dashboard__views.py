"""
apps/api/student_dashboard/views.py  — COMPLETE FIXED VERSION

Bugs fixed vs original:
  1. r.score → r.marks_obtained          (StudentTestResult has marks_obtained, not score)
  2. r.test.max_score → r.test.total_marks (Test has total_marks, not max_score)
  3. r.test.test_date → r.test.scheduled_on (Test has scheduled_on DateField, not test_date)
  4. .order_by("-test__test_date") → .order_by("-test__scheduled_on")
  5. ClassSession has no subject FK — sessions are not subject-aware; removed that field
  6. StudentAttendance.enrollment lookup used wrong related name
"""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsStudentOrParent
from apps.common.tenant import get_tenant_context
from apps.academics.models import (
    StudentProfile, BatchEnrollment, EnrollmentStatus,
)
from apps.assessments.models import (
    Homework, HomeworkStatus, HomeworkSubmission, StudentTestResult,
)
from apps.attendance.models import (
    ClassSession, StudentAttendance, AttendanceStatus,
)
from apps.billing.models import FeeInvoice, InvoiceStatus


class StudentDashboardView(APIView):
    """
    GET /api/student-dashboard/

    Comprehensive student home screen data in one call.
    Replaces 5+ separate API calls on every app open.

    Permission: IsStudentOrParent

    Headers: Authorization, X-Org, X-Branch

    Response:
    {
      "student":             { name, admission_no, branch_name, public_id },
      "today_sessions":      [{ id, batch_name, start_time, end_time, status }],
      "attendance_summary":  { present, absent, late, total_sessions, pct, period_days },
      "pending_homework":    [{ id, title, due_date, batch_name, subject, overdue }],
      "recent_test_results": [{ test_name, batch_name, subject, marks_obtained, total_marks, grade, scheduled_on }],
      "fee_summary":         { total_due, pending_invoice_count, upcoming_due_date, last_paid_amount },
      "generated_at":        datetime
    }
    """
    permission_classes = [IsStudentOrParent]

    def get(self, request):
        ctx   = get_tenant_context(request)
        today = timezone.localdate()

        # ── 1. Resolve student profile ────────────────────────────────────────
        student = (
            StudentProfile.objects
            .select_related("user")
            .filter(
                user=request.user,
                organisation=ctx.organisation,
                branch=ctx.branch,
            )
            .first()
        )
        if not student:
            return Response(
                {"detail": "Student profile not found for this branch."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── 2. Active enrolled batch IDs ──────────────────────────────────────
        enrolled_batch_ids = list(
            BatchEnrollment.objects
            .filter(student=student, status=EnrollmentStatus.ACTIVE)
            .values_list("batch_id", flat=True)
        )

        # ── 3. Today's sessions (no subject on ClassSession — batch-level only) ─
        today_sessions = (
            ClassSession.objects
            .filter(batch_id__in=enrolled_batch_ids, session_date=today)
            .select_related("batch")
            .order_by("start_time")
        )
        # FIX: ClassSession has no subject FK — removed subject field
        today_sessions_data = [
            {
                "id":         s.id,
                "batch_name": s.batch.name,
                "start_time": str(s.start_time) if s.start_time else None,
                "end_time":   str(s.end_time)   if s.end_time   else None,
                "status":     s.status,
            }
            for s in today_sessions
        ]

        # ── 4. Attendance summary (last 30 days) ──────────────────────────────
        att_start = today - timedelta(days=30)
        att_agg   = (
            StudentAttendance.objects
            .filter(
                student=student,
                session__session_date__gte=att_start,
                session__session_date__lte=today,
            )
            .aggregate(
                present=Count("id", filter=Q(status=AttendanceStatus.PRESENT)),
                absent=Count("id",  filter=Q(status=AttendanceStatus.ABSENT)),
                late=Count("id",    filter=Q(status=AttendanceStatus.LATE)),
                total=Count("id"),
            )
        )
        total_sessions = att_agg["total"]   or 0
        present        = att_agg["present"] or 0
        att_pct        = round(present / total_sessions * 100, 1) if total_sessions > 0 else 0.0

        attendance_summary = {
            "present":        present,
            "absent":         att_agg["absent"] or 0,
            "late":           att_agg["late"]   or 0,
            "total_sessions": total_sessions,
            "pct":            att_pct,
            "period_days":    30,
        }

        # ── 5. Pending homework (published, not yet submitted) ─────────────────
        submitted_hw_ids = set(
            HomeworkSubmission.objects
            .filter(student=student)
            .values_list("homework_id", flat=True)
        )
        pending_hw = (
            Homework.objects
            .filter(
                batch_id__in=enrolled_batch_ids,
                status=HomeworkStatus.PUBLISHED,
            )
            .exclude(id__in=submitted_hw_ids)
            .select_related("batch", "subject")
            .order_by("due_date")[:5]
        )
        pending_homework_data = [
            {
                "id":         hw.id,
                "title":      hw.title,
                "due_date":   hw.due_date.isoformat() if hw.due_date else None,
                "batch_name": hw.batch.name,
                "subject":    hw.subject.name if hw.subject else "",
                "overdue":    bool(hw.due_date and hw.due_date < today),
            }
            for hw in pending_hw
        ]

        # ── 6. Recent test results ─────────────────────────────────────────────
        # FIX: use correct field names from StudentTestResult + Test models
        #   - marks_obtained (not score)
        #   - total_marks (not max_score)
        #   - scheduled_on (not test_date)
        recent_results = (
            StudentTestResult.objects
            .filter(student=student)
            .select_related("test", "test__batch", "test__subject")
            .order_by("-test__scheduled_on", "-created_at")[:5]   # FIX: scheduled_on
        )
        recent_results_data = [
            {
                "test_name":      r.test.name,
                "batch_name":     r.test.batch.name,
                "subject":        r.test.subject.name if r.test.subject else "",
                "marks_obtained": str(r.marks_obtained),   # FIX: was r.score
                "total_marks":    str(r.test.total_marks), # FIX: was r.test.max_score
                "grade":          r.grade or "",
                "scheduled_on":   r.test.scheduled_on.isoformat() if r.test.scheduled_on else None,  # FIX: was test_date
            }
            for r in recent_results
        ]

        # ── 7. Fee summary ────────────────────────────────────────────────────
        due_qs    = FeeInvoice.objects.filter(student=student, status=InvoiceStatus.DUE)
        total_due = due_qs.aggregate(t=Sum("amount"))["t"] or 0
        next_due  = due_qs.order_by("due_date").values("due_date").first()
        last_paid = (
            FeeInvoice.objects
            .filter(student=student, status=InvoiceStatus.PAID)
            .order_by("-updated_at")
            .values("amount")
            .first()
        )

        fee_summary = {
            "total_due":             str(total_due),
            "pending_invoice_count": due_qs.count(),
            "upcoming_due_date":     next_due["due_date"].isoformat() if next_due else None,
            "last_paid_amount":      str(last_paid["amount"]) if last_paid else None,
        }

        return Response(
            {
                "student": {
                    "name":         student.user.full_name or student.user.mobile,
                    "admission_no": student.admission_no,
                    "branch_name":  ctx.branch.name if ctx.branch else "",
                    "public_id":    student.public_id,
                },
                "today_sessions":      today_sessions_data,
                "attendance_summary":  attendance_summary,
                "pending_homework":    pending_homework_data,
                "recent_test_results": recent_results_data,
                "fee_summary":         fee_summary,
                "generated_at":        timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK,
        )
