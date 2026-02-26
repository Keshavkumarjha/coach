"""
orgs/api/views.py

Organisation and Branch management.

Endpoints
─────────
GET   /api/org/me/         Retrieve current org profile
PATCH /api/org/me/         Update org name / contact info

GET   /api/branches/       List branches for this org
POST  /api/branches/       Create branch
GET   /api/branches/{id}/  Retrieve branch
PATCH /api/branches/{id}/  Update branch (incl. geo center)
DEL   /api/branches/{id}/  Delete branch
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.common.mixins import StandardPagination
from apps.orgs.models import Organisation, Branch
from apps.orgs.api.serializers import OrganisationSerializer, BranchSerializer
from apps.orgs.api.permissions import IsOrgOwnerByMobile


class OrganisationMeView(APIView):
    """
    GET  /api/org/me/   → returns the organisation owned by the request user
    PATCH /api/org/me/  → updates name, owner_name, etc.

    Permission: IsOrgOwnerByMobile — user's mobile must match org.owner_mobile
    """
    permission_classes = [IsAuthenticated, IsOrgOwnerByMobile]

    def _get_org(self, user) -> Organisation | None:
        mobile = getattr(user, "mobile", None)
        return Organisation.objects.filter(owner_mobile=mobile).first()

    def get(self, request):
        org = self._get_org(request.user)
        if not org:
            return Response(
                {"detail": "Organisation not found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(OrganisationSerializer(org).data, status=status.HTTP_200_OK)

    def patch(self, request):
        org = self._get_org(request.user)
        if not org:
            return Response(
                {"detail": "Organisation not found for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = OrganisationSerializer(org, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class BranchViewSet(ModelViewSet):
    """
    Full CRUD for Branches scoped to the owner org.

    Permission: IsOrgOwnerByMobile
    Pagination: StandardPagination (20/page)
    """
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, IsOrgOwnerByMobile]
    pagination_class = StandardPagination

    def _get_owner_org(self) -> Organisation | None:
        mobile = getattr(self.request.user, "mobile", None)
        return Organisation.objects.filter(owner_mobile=mobile).first()

    def get_queryset(self):
        org = self._get_owner_org()
        if not org:
            return Branch.objects.none()
        return Branch.objects.filter(organisation=org).order_by("-created_at")

    def perform_create(self, serializer):
        org = self._get_owner_org()
        serializer.save(organisation=org)
