"""
idcards/api/views.py

ID card templates and bulk generation.

Endpoints
─────────
GET/POST        /api/idcard-templates/
GET/PATCH/DEL   /api/idcard-templates/{id}/

GET             /api/idcards/
POST            /api/idcards/generate/    Bulk generate for students/teachers
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet
from apps.common.permissions import IsBranchAdmin
from apps.idcards.models import IdCardTemplate, GeneratedIdCard
from apps.idcards.api.serializers import (
    IdCardTemplateSerializer,
    GenerateIdCardSerializer,
    GeneratedIdCardSerializer,
)


class IdCardTemplateViewSet(TenantViewSet):
    """
    CRUD for ID card design templates.

    Templates are scoped to the org (not branch-level),
    so they can be shared across branches of the same org.

    Permissions: IsBranchAdmin (all actions)
    """
    serializer_class = IdCardTemplateSerializer
    permission_classes = [IsBranchAdmin]
    queryset = IdCardTemplate.objects.all()
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        # Templates are org-scoped, not branch-scoped
        ctx = self.get_tenant()
        return IdCardTemplate.objects.filter(
            organisation=ctx.organisation,
        ).order_by(*self.ordering)

    def perform_create(self, serializer):
        ctx = self.get_tenant()
        serializer.save(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=self.request.user,
        )


class GeneratedIdCardViewSet(TenantViewSet):
    """
    List generated ID cards and trigger bulk generation.

    Permissions: IsBranchAdmin (all actions)

    Custom actions:
        POST /api/idcards/generate/
        Body: {
            "template_id": 1,
            "student_public_ids": ["STU-26-0000001", ...],  // optional
            "teacher_public_ids": ["TCH-26-0000001", ...]   // optional
        }
    """
    serializer_class = GeneratedIdCardSerializer
    permission_classes = [IsBranchAdmin]
    queryset = GeneratedIdCard.objects.select_related(
        "student", "student__user",
        "teacher", "teacher__user",
        "template",
    ).all()
    ordering = ["-created_at"]
    http_method_names = ["get", "post"]

    def get_queryset(self):
        ctx = self.get_tenant()
        return (
            GeneratedIdCard.objects
            .filter(template__organisation=ctx.organisation)
            .select_related(
                "student", "student__user",
                "teacher", "teacher__user",
                "template",
            )
            .order_by(*self.ordering)
        )

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        """
        POST /api/idcards/generate/
        Bulk-generates ID cards for the given students and/or teachers.
        """
        serializer = GenerateIdCardSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {"message": "ID cards generated.", **result},
            status=status.HTTP_200_OK,
        )
