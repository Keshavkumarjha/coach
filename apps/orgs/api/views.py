from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.orgs.models import Organisation, Branch
from apps.orgs.api.serializers import OrganisationSerializer, BranchSerializer
from apps.orgs.api.permissions import IsOrgOwnerByMobile


def get_owner_org(user) -> Organisation:
    mobile = getattr(user, "mobile", None)
    return Organisation.objects.filter(owner_mobile=mobile).first()


class OrganisationMeView(APIView):
    """
    GET  /api/org/me/     -> org profile
    PATCH /api/org/me/    -> update org profile
    """
    permission_classes = [IsAuthenticated, IsOrgOwnerByMobile]

    def get(self, request):
        org = get_owner_org(request.user)
        if not org:
            return Response({"detail": "Organisation not found for this user."}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrganisationSerializer(org).data, status=status.HTTP_200_OK)

    def patch(self, request):
        org = get_owner_org(request.user)
        if not org:
            return Response({"detail": "Organisation not found for this user."}, status=status.HTTP_404_NOT_FOUND)

        s = OrganisationSerializer(org, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data, status=status.HTTP_200_OK)


class BranchViewSet(ModelViewSet):
    """
    /api/branches/
      GET, POST
    /api/branches/{id}/
      GET, PATCH, PUT, DELETE
    """
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, IsOrgOwnerByMobile]

    def get_queryset(self):
        org = get_owner_org(self.request.user)
        if not org:
            return Branch.objects.none()
        return Branch.objects.filter(organisation=org).order_by("-created_at")

    def perform_create(self, serializer):
        org = get_owner_org(self.request.user)
        serializer.save(organisation=org)