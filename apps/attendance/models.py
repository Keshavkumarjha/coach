from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel

try:
    from django.contrib.gis.db.models import PointField
except Exception:
    PointField = None


class SessionStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    CLOSED = "CLOSED", "Closed"
    CANCELLED = "CANCELLED", "Cancelled"


class ClassSession(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="sessions")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="sessions")
    batch = models.ForeignKey("academics.Batch", on_delete=models.CASCADE, related_name="sessions")

    session_date = models.DateField(db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=SessionStatus.choices, default=SessionStatus.OPEN, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions_created")

    # Student self-mark constraints (50m default, can override per session)
    allow_student_self_mark = models.BooleanField(default=True)
    max_self_mark_distance_m = models.PositiveIntegerField(default=50)

    class Meta:
        db_table = "att_class_session"
        constraints = [
            models.UniqueConstraint(fields=["batch", "session_date", "start_time"], name="uq_session_batch_date_time"),
        ]
        indexes = [
            models.Index(fields=["branch", "session_date"]),
            models.Index(fields=["batch", "session_date"]),
            models.Index(fields=["organisation", "session_date"]),
            models.Index(fields=["status", "session_date"]),
        ]


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT", "Present"
    ABSENT = "ABSENT", "Absent"
    LATE = "LATE", "Late"
    LEAVE = "LEAVE", "Leave"


class MarkedBy(models.TextChoices):
    TEACHER = "TEACHER", "Teacher"
    STUDENT_GEO = "STUDENT_GEO", "Student Geo"
    ADMIN = "ADMIN", "Admin"


class StudentAttendance(TimeStampedModel):
    """
    Large table: session x student.
    """
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="attendance_records")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="attendance_records")
    batch = models.ForeignKey("academics.Batch", on_delete=models.CASCADE, related_name="attendance_records")

    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name="attendance_records")
    student = models.ForeignKey("academics.StudentProfile", on_delete=models.CASCADE, related_name="attendance_records")

    status = models.CharField(max_length=10, choices=AttendanceStatus.choices, db_index=True)
    marked_by_type = models.CharField(max_length=12, choices=MarkedBy.choices, db_index=True)
    marked_by_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="attendance_marked")

    marked_at = models.DateTimeField(default=timezone.now, db_index=True)

    # Only filled if STUDENT_GEO
    if PointField:
        marked_location = PointField(geography=True, null=True, blank=True)
    else:
        marked_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
        marked_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    distance_from_branch_m = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "att_student_attendance"
        constraints = [
            models.UniqueConstraint(fields=["session", "student"], name="uq_session_student_attendance"),
        ]
        indexes = [
            models.Index(fields=["session", "status"]),
            models.Index(fields=["student", "marked_at"]),
            models.Index(fields=["branch", "marked_at"]),
            models.Index(fields=["batch", "marked_at"]),
        ]