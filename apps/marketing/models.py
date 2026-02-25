from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel
from apps.common.public_ids import campaign_public_id


class CampaignStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SCHEDULED = "SCHEDULED", "Scheduled"
    SENDING = "SENDING", "Sending"
    COMPLETED = "COMPLETED", "Completed"
    FAILED = "FAILED", "Failed"


class TargetGroup(models.TextChoices):
    ALL_STUDENTS = "ALL_STUDENTS", "All Students"
    ALL_PARENTS = "ALL_PARENTS", "All Parents"
    ALL_TEACHERS = "ALL_TEACHERS", "All Teachers"
    BATCHES = "BATCHES", "Selected Batches"


class WhatsAppCampaign(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=24, unique=True, db_index=True, editable=False)

    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="wa_campaigns")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="wa_campaigns")

    name = models.CharField(max_length=160, db_index=True)
    message = models.TextField()

    target_group = models.CharField(max_length=20, choices=TargetGroup.choices, db_index=True)
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(max_length=12, choices=CampaignStatus.choices, default=CampaignStatus.DRAFT, db_index=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="wa_campaigns_created")

    class Meta:
        db_table = "mkt_wa_campaign"
        indexes = [
            models.Index(fields=["branch", "status", "scheduled_at"]),
            models.Index(fields=["organisation", "status", "scheduled_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = campaign_public_id()
        super().save(*args, **kwargs)


class WhatsAppCampaignBatchTarget(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    campaign = models.ForeignKey(WhatsAppCampaign, on_delete=models.CASCADE, related_name="batch_targets")
    batch = models.ForeignKey("academics.Batch", on_delete=models.CASCADE, related_name="wa_campaign_targets")

    class Meta:
        db_table = "mkt_wa_campaign_batch_target"
        constraints = [models.UniqueConstraint(fields=["campaign", "batch"], name="uq_campaign_batch")]


class DeliveryStatus(models.TextChoices):
    QUEUED = "QUEUED", "Queued"
    SENT = "SENT", "Sent"
    DELIVERED = "DELIVERED", "Delivered"
    READ = "READ", "Read"
    FAILED = "FAILED", "Failed"


class WhatsAppMessageLog(TimeStampedModel):
    """
    High volume table. Partition monthly later if needed.
    """
    id = models.BigAutoField(primary_key=True)

    campaign = models.ForeignKey(WhatsAppCampaign, on_delete=models.CASCADE, related_name="message_logs")
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="wa_message_logs")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="wa_message_logs")

    to_mobile = models.CharField(max_length=15, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="wa_messages")

    status = models.CharField(max_length=12, choices=DeliveryStatus.choices, default=DeliveryStatus.QUEUED, db_index=True)
    provider_message_id = models.CharField(max_length=120, blank=True, db_index=True)
    error = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "mkt_wa_message_log"
        indexes = [
            models.Index(fields=["campaign", "status", "created_at"]),
            models.Index(fields=["branch", "status", "created_at"]),
            models.Index(fields=["to_mobile", "created_at"]),
        ]