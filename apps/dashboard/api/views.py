"""
apps/api/dashboard/views.py

Single endpoint that serves everything the admin dashboard needs in one call.

Endpoint
────────
GET /api/dashboard/

Required headers:
    Authorization: Bearer <access_token>
    X-Org:         ORG-26-000001
    X-Branch:      BR-26-000001   (optional — falls back to membership branch)

Query params:
    (none yet — trend_days planned for v2)

Response: DashboardResponseSerializer payload
    - 4 stat cards  (revenue, students, batches, pending approvals)
    - revenue trend line chart  (30-day daily)
    - revenue by batch donut chart  (top 8)
    - pending fee transactions table
    - recent activity feed

Permission: IsBranchAdmin  (ORG_OWNER | ORG_ADMIN | BRANCH_ADMIN)
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsBranchAdmin
from apps.common.tenant import get_tenant_context
from apps.api.dashboard.serializers import DashboardResponseSerializer
from apps.api.dashboard.service import DashboardService


class AdminDashboardView(APIView):
    """
    GET /api/dashboard/

    Instantiates DashboardService for the current (org, branch) and returns
    the full serialized payload in a single response.

    All DB queries are in DashboardService — this view stays thin.
    """
    permission_classes = [IsBranchAdmin]

    def get(self, request):
        ctx = get_tenant_context(request)
        branch = ctx.branch or self._fallback_branch(ctx)

        data = DashboardService(ctx.organisation, branch).build()
        serializer = DashboardResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @staticmethod
    def _fallback_branch(ctx):
        """If X-Branch header was omitted, fall back to the user's membership branch."""
        return ctx.membership.branch
