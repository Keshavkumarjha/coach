from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.tenant import get_tenant_context
from apps.common.permissions import IsBranchAdmin
from apps.accounts.models import BranchJoinRequest, JoinStatus
from apps.accounts.api.serializers_admin import (
    JoinRequestSerializer,
    JoinApproveSerializer,
    JoinRejectSerializer,
     )


class JoinRequestAdminViewSet(ModelViewSet):
    """
    Admin dashboard:
    - list pending join requests
    - approve/reject
    """
    serializer_class = JoinRequestSerializer
    permission_classes = [IsBranchAdmin]
    http_method_names = ["get", "post"]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        qs = BranchJoinRequest.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).order_by("-created_at")

        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=True, methods=["post"], permission_classes=[IsBranchAdmin], url_path="approve")
    def approve(self, request, pk=None):
        jr = self.get_object()
        s = JoinApproveSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        out = s.save(request=request, join_request=jr)
        return Response(out, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsBranchAdmin], url_path="reject")
    def reject(self, request, pk=None):
        jr = self.get_object()
        s = JoinRejectSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        out = s.save(request=request, join_request=jr)
        return Response(out, status=status.HTTP_200_OK)