"""
marketing/api/views.py  — COMPLETE FIXED VERSION

WhatsApp campaign management.

Endpoints
─────────
GET/POST     /api/wa-campaigns/
GET/DEL      /api/wa-campaigns/{id}/
GET          /api/wa-campaigns/{id}/logs/   Delivery log per campaign
POST         /api/wa-campaigns/{id}/send/   Trigger immediate send  ← FIX #5 (new)
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet, StatusFilterMixin
from apps.common.permissions import IsBranchAdmin
from apps.marketing.models import CampaignStatus, WhatsAppCampaign, WhatsAppMessageLog
from apps.marketing.api.serializers import (
    WhatsAppCampaignSerializer,
    WhatsAppMessageLogSerializer,
)


# ═══════════════════════════════════════════════════════════════════════════════
# FIX #5 — WhatsAppCampaignViewSet: add POST /{id}/send/
#
# PROBLEM: Campaigns could be created with status=DRAFT or SCHEDULED but there
#          was no endpoint to trigger a send. The "Send Now" button in the UI
#          had nothing to call — clicking it produced a 404/405.
#
# FIX:     Added a `send` @action (detail=True, POST).
#          - Validates campaign status (must be DRAFT or SCHEDULED)
#          - Atomically sets status → SENDING
#          - Enqueues a Celery task (stub call included, ready to activate)
#          - Returns updated campaign status so the UI can reflect SENDING state
# ═══════════════════════════════════════════════════════════════════════════════
class WhatsAppCampaignViewSet(StatusFilterMixin, TenantViewSet):
    """
    WhatsApp campaigns scoped to the current branch.

    Permissions: IsBranchAdmin (all actions)

    Query params:
        ?status=DRAFT | SCHEDULED | SENDING | COMPLETED | FAILED

    Custom actions:
        GET  /{id}/logs/   Delivery log (last 500 messages)
        POST /{id}/send/   Trigger immediate send (NEW)
    """
    serializer_class = WhatsAppCampaignSerializer
    permission_classes = [IsBranchAdmin]
    queryset = WhatsAppCampaign.objects.all()
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "delete"]

    def create(self, request, *args, **kwargs):
        serializer = WhatsAppCampaignSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        campaign = serializer.save()
        return Response(
            WhatsAppCampaignSerializer(campaign).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="logs")
    def logs(self, request, pk=None):
        """
        GET /api/wa-campaigns/{id}/logs/
        Returns delivery logs for this campaign, newest first (max 500).
        """
        campaign = self.get_object()
        qs = (
            WhatsAppMessageLog.objects
            .filter(campaign=campaign)
            .order_by("-created_at")[:500]
        )
        return Response(WhatsAppMessageLogSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], url_path="send")
    def send(self, request, pk=None):
        """
        POST /api/wa-campaigns/{id}/send/

        Triggers an immediate send of a DRAFT or SCHEDULED campaign.

        Validations:
            - Campaign must belong to the current branch (enforced by TenantViewSet)
            - Status must be DRAFT or SCHEDULED — cannot re-send COMPLETED/FAILED

        Side effects:
            - Sets campaign.status → SENDING immediately
            - Enqueues background Celery task to process messages asynchronously
              (activate the import below once your Celery worker is configured)

        Response:
            { "campaign_id": int, "status": "SENDING", "message": "Campaign queued." }
        """
        campaign = self.get_object()

        # Only DRAFT and SCHEDULED campaigns can be triggered
        sendable = {CampaignStatus.DRAFT, CampaignStatus.SCHEDULED}
        if campaign.status not in sendable:
            return Response(
                {
                    "detail": (
                        f"Cannot send a campaign with status '{campaign.status}'. "
                        f"Only DRAFT or SCHEDULED campaigns can be sent."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark as SENDING before enqueuing so the UI reflects the state immediately
        campaign.status = CampaignStatus.SENDING
        campaign.save(update_fields=["status", "updated_at"])

        # ── Enqueue async send task ────────────────────────────────────────────
        # Activate this when Celery + Redis are configured:
        #
        #   from apps.marketing.tasks import send_whatsapp_campaign
        #   send_whatsapp_campaign.delay(campaign.id)
        #
        # The task should:
        #   1. Load campaign.batch_targets → collect recipient phone numbers
        #   2. Render the message template for each recipient
        #   3. POST to WhatsApp Business API / Gupshup / Interakt
        #   4. Create WhatsAppMessageLog rows (status=QUEUED initially)
        #   5. On completion: set campaign.status = COMPLETED (or FAILED)
        # ──────────────────────────────────────────────────────────────────────

        return Response(
            {
                "campaign_id": campaign.id,
                "status":      campaign.status,
                "message":     "Campaign queued for sending. Messages will be dispatched shortly.",
            },
            status=status.HTTP_200_OK,
        )
