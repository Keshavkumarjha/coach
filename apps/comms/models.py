from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.common.public_ids import announcement_public_id


class AudienceType(models.TextChoices):
    ALL_STUDENTS = "ALL_STUDENTS", "All Students"
    ALL_PARENTS = "ALL_PARENTS", "All Parents"
    ALL_TEACHERS = "ALL_TEACHERS", "All Teachers"
    BATCHES = "BATCHES", "Selected Batches"
    BRANCH = "BRANCH", "Branch Wide"


class Announcement(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=24, unique=True, db_index=True, editable=False)

    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="announcements")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="announcements")

    title = models.CharField(max_length=140, db_index=True)
    message = models.TextField()

    audience_type = models.CharField(max_length=20, choices=AudienceType.choices, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="announcements_created")

    is_pinned = models.BooleanField(default=False, db_index=True)
    published_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "com_announcement"
        indexes = [
            models.Index(fields=["branch", "published_at"]),
            models.Index(fields=["organisation", "published_at"]),
            models.Index(fields=["branch", "is_pinned", "published_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = announcement_public_id()
        super().save(*args, **kwargs)


class AnnouncementBatchTarget(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name="batch_targets")
    batch = models.ForeignKey("academics.Batch", on_delete=models.CASCADE, related_name="announcement_targets")

    class Meta:
        db_table = "com_announcement_batch_target"
        constraints = [models.UniqueConstraint(fields=["announcement", "batch"], name="uq_announcement_batch")]


class NotificationType(models.TextChoices):
    ANNOUNCEMENT = "ANNOUNCEMENT", "Announcement"
    FEE = "FEE", "Fee"
    ATTENDANCE = "ATTENDANCE", "Attendance"
    TEST = "TEST", "Test"
    GENERAL = "GENERAL", "General"


class UserNotification(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")

    ntype = models.CharField(max_length=15, choices=NotificationType.choices, db_index=True)
    title = models.CharField(max_length=140)
    body = models.TextField(blank=True)

    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "com_user_notification"
        indexes = [models.Index(fields=["user", "is_read", "created_at"])]