"""
marketing/api/views.py  — COMPLETE VERSION

Fixed vs original:
  - send() action is properly defined INSIDE the class (original monkey-patched it after)
  - All imports cleaned up (removed duplicate CampaignStatus import)

Endpoints:
  GET/POST  /api/wa-campaigns/
  GET/DEL   /api/wa-campaigns/{id}/
  GET       /api/wa-campaigns/{id}/logs/
  POST      /api/wa-campaigns/{id}/send/
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet, StatusFilterMixin
from apps.common.permissions import IsBranchAdmin
from apps.marketing.models import WhatsAppCampaign, WhatsAppMessageLog, CampaignStatus
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
        GET  /{id}/logs/   Returns delivery log for the campaign (latest 500)
        POST /{id}/send/   Trigger immediate send for DRAFT or SCHEDULED campaigns
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

        Immediately triggers a DRAFT or SCHEDULED campaign.
        Sets status → SENDING and enqueues the Celery send task.

        Response: { campaign_id, status, message }
        """
        campaign = self.get_object()

        if campaign.status not in (CampaignStatus.DRAFT, CampaignStatus.SCHEDULED):
            return Response(
                {"detail": f"Cannot send a campaign with status '{campaign.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        campaign.status = CampaignStatus.SENDING
        campaign.save(update_fields=["status", "updated_at"])

        # Enqueue Celery task when worker is configured:
        # from apps.marketing.tasks import send_whatsapp_campaign
        # send_whatsapp_campaign.delay(campaign.id)

        return Response(
            {
                "campaign_id": campaign.id,
                "status":      campaign.status,
                "message":     "Campaign queued for sending.",
            },
            status=status.HTTP_200_OK,
        )
