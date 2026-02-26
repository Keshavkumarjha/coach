"""
accounts/api/views_admin.py

Admin-only ViewSet for managing BranchJoinRequests.

Endpoints
─────────
GET  /api/join-requests/              List all requests (filterable by ?status=)
GET  /api/join-requests/{id}/         Retrieve single request
POST /api/join-requests/{id}/approve/ Approve → creates membership + profile
POST /api/join-requests/{id}/reject/  Reject → marks as REJECTED
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet, StatusFilterMixin, ApproveRejectMixin
from apps.common.permissions import IsBranchAdmin
from apps.accounts.models import BranchJoinRequest, JoinStatus
from apps.accounts.api.serializers_admin import (
    JoinRequestSerializer,
    JoinApproveSerializer,
    JoinRejectSerializer,
)


class JoinRequestAdminViewSet(StatusFilterMixin, ApproveRejectMixin, TenantViewSet):
    """
    Admin ViewSet for BranchJoinRequest.

    Inherits:
        StatusFilterMixin    → ?status=PENDING / APPROVED / REJECTED
        ApproveRejectMixin   → POST …/{id}/approve/ and …/{id}/reject/
        TenantViewSet        → pagination + org/branch scoping

    Approve flow:
        POST /api/join-requests/{id}/approve/
        Body: { "note": "ok", "batch_id": 12 }   (note + batch_id are optional)

    Reject flow:
        POST /api/join-requests/{id}/reject/
        Body: { "note": "Duplicate request" }
    """
    serializer_class = JoinRequestSerializer
    permission_classes = [IsBranchAdmin]
    http_method_names = ["get", "post"]
    queryset = BranchJoinRequest.objects.select_related("branch", "organisation").all()
    ordering = ["-created_at"]

    # ── ApproveRejectMixin hooks ──────────────────────────────────────────────

    def _do_approve(self, request, obj: BranchJoinRequest) -> dict:
        serializer = JoinApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.save(request=request, join_request=obj)

    def _do_reject(self, request, obj: BranchJoinRequest) -> dict:
        serializer = JoinRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.save(request=request, join_request=obj)
