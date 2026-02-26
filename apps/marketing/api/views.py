"""
marketing/api/views.py

WhatsApp campaign management.

Endpoints
─────────
GET/POST     /api/wa-campaigns/
GET/DEL      /api/wa-campaigns/{id}/
GET          /api/wa-campaigns/{id}/logs/   Delivery log per campaign
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet, StatusFilterMixin
from apps.common.permissions import IsBranchAdmin
from apps.marketing.models import WhatsAppCampaign, WhatsAppMessageLog
from apps.marketing.api.serializers import (
    WhatsAppCampaignSerializer,
    WhatsAppMessageLogSerializer,
)


class WhatsAppCampaignViewSet(StatusFilterMixin, TenantViewSet):
    """
    WhatsApp campaigns scoped to the current branch.

    Permissions: IsBranchAdmin (all actions)

    Query params:
        ?status=DRAFT | SCHEDULED | SENDING | COMPLETED | FAILED

    Custom actions:
        GET /{id}/logs/   Returns delivery log for the campaign (latest 500)
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
