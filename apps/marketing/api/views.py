from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.tenant import get_tenant_context
from apps.common.permissions import IsBranchAdmin
from apps.marketing.models import WhatsAppCampaign, WhatsAppMessageLog

from apps.marketing.api.serializers import WhatsAppCampaignSerializer, WhatsAppMessageLogSerializer


class WhatsAppCampaignViewSet(ModelViewSet):
    serializer_class = WhatsAppCampaignSerializer
    permission_classes = [IsBranchAdmin]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return WhatsAppCampaign.objects.filter(organisation=ctx.organisation, branch=ctx.branch).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        camp = s.save()
        return Response(WhatsAppCampaignSerializer(camp).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], permission_classes=[IsBranchAdmin], url_path="logs")
    def logs(self, request, pk=None):
        ctx = get_tenant_context(request)
        camp = self.get_object()
        qs = WhatsAppMessageLog.objects.filter(campaign=camp).order_by("-created_at")[:500]
        return Response(WhatsAppMessageLogSerializer(qs, many=True).data)