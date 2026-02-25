from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.common.public_ids import student_public_id, teacher_public_id


class BatchStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ARCHIVED = "ARCHIVED", "Archived"


class Batch(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="batches")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="batches")

    name = models.CharField(max_length=120, db_index=True)
    code = models.CharField(max_length=24, db_index=True)
    status = models.CharField(max_length=10, choices=BatchStatus.choices, default=BatchStatus.ACTIVE, db_index=True)

    # optional attendance window
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    days_of_week = models.CharField(max_length=20, blank=True)  # "Mon,Tue,Wed"

    class Meta:
        db_table = "acad_batch"
        constraints = [
            models.UniqueConstraint(fields=["branch", "code"], name="uq_batch_branch_code"),
        ]
        indexes = [
            models.Index(fields=["organisation", "branch", "status"]),
            models.Index(fields=["branch", "status"]),
        ]


class TeacherProfile(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=22, unique=True, db_index=True, editable=False)

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="teacher_profile")
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="teachers")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="teachers")

    employee_id = models.CharField(max_length=32, blank=True, db_index=True)
    designation = models.CharField(max_length=60, blank=True)
    is_active_for_login = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "acad_teacher_profile"
        indexes = [
            models.Index(fields=["branch", "is_active_for_login"]),
            models.Index(fields=["organisation", "branch"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = teacher_public_id()
        super().save(*args, **kwargs)


class StudentProfile(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=22, unique=True, db_index=True, editable=False)

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="student_profile")
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="students")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="students")

    admission_no = models.CharField(max_length=32, db_index=True)
    roll_no = models.CharField(max_length=20, blank=True, db_index=True)

    is_active_for_login = models.BooleanField(default=False, db_index=True)  # approved by admin

    class Meta:
        db_table = "acad_student_profile"
        constraints = [
            models.UniqueConstraint(fields=["organisation", "admission_no"], name="uq_student_org_admno"),
        ]
        indexes = [
            models.Index(fields=["branch", "is_active_for_login"]),
            models.Index(fields=["organisation", "branch"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = student_public_id()
        super().save(*args, **kwargs)


class ParentProfile(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="parent_profile")
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="parents")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="parents")

    is_active_for_login = models.BooleanField(default=False, db_index=True)  # approved

    class Meta:
        db_table = "acad_parent_profile"
        indexes = [
            models.Index(fields=["branch", "is_active_for_login"]),
        ]


class StudentParentLink(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="parent_links")
    parent = models.ForeignKey(ParentProfile, on_delete=models.CASCADE, related_name="student_links")
    relation = models.CharField(max_length=30, blank=True)

    class Meta:
        db_table = "acad_student_parent_link"
        constraints = [
            models.UniqueConstraint(fields=["student", "parent"], name="uq_student_parent"),
        ]


class EnrollmentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    LEFT = "LEFT", "Left"
    PAUSED = "PAUSED", "Paused"


class BatchEnrollment(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="enrollments")
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name="enrollments")

    status = models.CharField(max_length=10, choices=EnrollmentStatus.choices, default=EnrollmentStatus.ACTIVE, db_index=True)
    joined_on = models.DateField(default=timezone.localdate)
    left_on = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "acad_batch_enrollment"
        constraints = [
            models.UniqueConstraint(fields=["batch", "student"], name="uq_batch_student"),
        ]
        indexes = [
            models.Index(fields=["batch", "status"]),
            models.Index(fields=["student", "status"]),
        ]


class Weekday(models.IntegerChoices):
    MON = 1, "Mon"
    TUE = 2, "Tue"
    WED = 3, "Wed"
    THU = 4, "Thu"
    FRI = 5, "Fri"
    SAT = 6, "Sat"
    SUN = 7, "Sun"


class Subject(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="subjects")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="subjects")
    name = models.CharField(max_length=80, db_index=True)

    class Meta:
        db_table = "acad_subject"
        constraints = [
            models.UniqueConstraint(fields=["branch", "name"], name="uq_subject_branch_name"),
        ]


class TimeTableSlot(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="timetable_slots")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="timetable_slots")
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name="timetable_slots")

    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices, db_index=True)
    start_time = models.TimeField(db_index=True)
    end_time = models.TimeField(db_index=True)

    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="timetable_slots")
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="timetable_slots")
    room = models.CharField(max_length=40, blank=True)

    class Meta:
        db_table = "acad_timetable_slot"
        indexes = [
            models.Index(fields=["batch", "weekday", "start_time"]),
            models.Index(fields=["branch", "weekday", "start_time"]),
        ]