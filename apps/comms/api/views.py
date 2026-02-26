"""
comms/api/views.py

Announcements for students, parents, and teachers.

Endpoints
─────────
GET/POST        /api/announcements/
GET/PATCH/DEL   /api/announcements/{id}/
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet, StatusFilterMixin
from apps.common.permissions import IsBranchAdmin, IsStudentOrParent
from apps.comms.models import Announcement
from apps.comms.api.serializers import AnnouncementSerializer


class AnnouncementViewSet(TenantViewSet):
    """
    Announcements scoped to the current branch.

    Permissions:
        create / update / delete  → IsBranchAdmin
        list / retrieve           → IsStudentOrParent

    Query params:
        ?is_pinned=true       Only pinned announcements
        ?audience_type=BATCHES | ALL_STUDENTS | ALL_PARENTS | ALL_TEACHERS | BRANCH
    """
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.prefetch_related("batch_targets").all()
    ordering = ["-is_pinned", "-published_at"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsBranchAdmin()]
        return [IsStudentOrParent()]

    def get_queryset(self):
        qs = super().get_queryset()
        is_pinned = self.request.query_params.get("is_pinned")
        if is_pinned and is_pinned.lower() == "true":
            qs = qs.filter(is_pinned=True)
        audience_type = self.request.query_params.get("audience_type")
        if audience_type:
            qs = qs.filter(audience_type=audience_type.upper())
        return qs

    def create(self, request, *args, **kwargs):
        serializer = AnnouncementSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        announcement = serializer.save()
        return Response(
            AnnouncementSerializer(announcement).data,
            status=status.HTTP_201_CREATED,
        )
