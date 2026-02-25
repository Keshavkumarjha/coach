from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class ReviewStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class Review(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="reviews")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews")

    author_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews_written")
    author_name = models.CharField(max_length=120, blank=True)
    author_mobile = models.CharField(max_length=15, blank=True, db_index=True)

    rating = models.PositiveSmallIntegerField(db_index=True)  # 1..5
    title = models.CharField(max_length=140, blank=True)
    comment = models.TextField(blank=True)

    status = models.CharField(max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.PENDING, db_index=True)
    moderated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews_moderated")
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "rev_review"
        indexes = [
            models.Index(fields=["organisation", "status", "created_at"]),
            models.Index(fields=["branch", "status", "created_at"]),
            models.Index(fields=["organisation", "rating"]),
        ]