from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class StudyMaterial(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="materials")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="materials")
    batch = models.ForeignKey("academics.Batch", on_delete=models.CASCADE, related_name="materials")

    title = models.CharField(max_length=160, db_index=True)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to="materials/", null=True, blank=True)
    link_url = models.URLField(blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="materials_created")

    class Meta:
        db_table = "assess_material"
        indexes = [
            models.Index(fields=["batch", "created_at"]),
            models.Index(fields=["branch", "created_at"]),
        ]


class HomeworkStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    CLOSED = "CLOSED", "Closed"


class Homework(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="homeworks")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="homeworks")
    batch = models.ForeignKey("academics.Batch", on_delete=models.CASCADE, related_name="homeworks")
    subject = models.ForeignKey("academics.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="homeworks")

    title = models.CharField(max_length=160, db_index=True)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True, db_index=True)

    status = models.CharField(max_length=10, choices=HomeworkStatus.choices, default=HomeworkStatus.PUBLISHED, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="homeworks_created")

    attachment = models.FileField(upload_to="homework/", null=True, blank=True)

    class Meta:
        db_table = "assess_homework"
        indexes = [
            models.Index(fields=["batch", "status", "due_date"]),
            models.Index(fields=["branch", "status", "created_at"]),
        ]


class HomeworkSubmissionStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    LATE = "LATE", "Late"
    CHECKED = "CHECKED", "Checked"


class HomeworkSubmission(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey("academics.StudentProfile", on_delete=models.CASCADE, related_name="homework_submissions")

    text_answer = models.TextField(blank=True)
    file_answer = models.FileField(upload_to="homework/submissions/", null=True, blank=True)

    status = models.CharField(max_length=10, choices=HomeworkSubmissionStatus.choices, default=HomeworkSubmissionStatus.SUBMITTED, db_index=True)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="homework_checked")
    marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    feedback = models.CharField(max_length=300, blank=True)

    class Meta:
        db_table = "assess_homework_submission"
        constraints = [models.UniqueConstraint(fields=["homework", "student"], name="uq_homework_student")]
        indexes = [
            models.Index(fields=["student", "created_at"]),
            models.Index(fields=["homework", "status"]),
        ]


class TestType(models.TextChoices):
    UNIT = "UNIT", "Unit Test"
    MOCK = "MOCK", "Mock"
    FINAL = "FINAL", "Final"
    CUSTOM = "CUSTOM", "Custom"


class TestStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PUBLISHED = "PUBLISHED", "Published"
    COMPLETED = "COMPLETED", "Completed"


class Test(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="tests")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="tests")
    batch = models.ForeignKey("academics.Batch", on_delete=models.CASCADE, related_name="tests")
    subject = models.ForeignKey("academics.Subject", on_delete=models.SET_NULL, null=True, blank=True, related_name="tests")

    name = models.CharField(max_length=160, db_index=True)
    test_type = models.CharField(max_length=10, choices=TestType.choices, default=TestType.CUSTOM, db_index=True)

    scheduled_on = models.DateField(null=True, blank=True, db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    duration_min = models.PositiveIntegerField(default=60)

    total_marks = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    passing_marks = models.DecimalField(max_digits=7, decimal_places=2, default=0)

    status = models.CharField(max_length=12, choices=TestStatus.choices, default=TestStatus.PUBLISHED, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="tests_created")

    class Meta:
        db_table = "assess_test"
        indexes = [
            models.Index(fields=["batch", "status", "scheduled_on"]),
            models.Index(fields=["branch", "status", "scheduled_on"]),
        ]


class StudentTestResult(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name="results")
    student = models.ForeignKey("academics.StudentProfile", on_delete=models.CASCADE, related_name="test_results")

    marks_obtained = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    grade = models.CharField(max_length=10, blank=True)
    remarks = models.CharField(max_length=200, blank=True)

    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="results_entered")

    class Meta:
        db_table = "assess_student_test_result"
        constraints = [models.UniqueConstraint(fields=["test", "student"], name="uq_test_student")]
        indexes = [
            models.Index(fields=["student", "created_at"]),
            models.Index(fields=["test", "marks_obtained"]),
        ]