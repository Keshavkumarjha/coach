from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import AllowAny

from apps.common.tenant import get_tenant_context
from apps.common.permissions import IsBranchAdmin
from apps.reviews.models import Review, ReviewStatus
from apps.reviews.api.serializers import ReviewSerializer, ReviewModerateSerializer


class ReviewViewSet(ModelViewSet):
    """
    - Public create (AllowAny) to submit review
    - Admin lists + approve/reject
    """
    serializer_class = ReviewSerializer
    http_method_names = ["get", "post", "delete"]

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsBranchAdmin()]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return Review.objects.filter(organisation=ctx.organisation, branch=ctx.branch).order_by("-created_at")

    def perform_create(self, serializer):
        # Public create needs org/branch context - accept org/branch via request headers or query
        # For public endpoints, you can also accept branch public_id in body (recommended).
        raise NotImplementedError("Use /reviews/public-submit/")

    @action(detail=False, methods=["post"], permission_classes=[AllowAny], url_path="public-submit")
    def public_submit(self, request):
        """
        POST /api/reviews/public-submit/?org=ORG-..&branch=BR-..
        body: {author_name, author_mobile, rating, title, comment}
        """
        # For AllowAny, tenant helper needs auth; so read org/branch manually:
        from rest_framework.exceptions import ValidationError
        from apps.orgs.models import Organisation, Branch

        org_pid = request.query_params.get("org") or request.headers.get("X-Org")
        br_pid = request.query_params.get("branch") or request.headers.get("X-Branch")
        if not org_pid or not br_pid:
            raise ValidationError({"detail": "org and branch required."})

        org = Organisation.objects.filter(public_id=org_pid).first()
        br = Branch.objects.filter(public_id=br_pid, organisation=org).first() if org else None
        if not org or not br:
            raise ValidationError({"detail": "Invalid org/branch."})

        s = ReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        rv = Review.objects.create(
            organisation=org,
            branch=br,
            author_name=s.validated_data.get("author_name", ""),
            author_mobile=s.validated_data.get("author_mobile", ""),
            rating=s.validated_data["rating"],
            title=s.validated_data.get("title", ""),
            comment=s.validated_data.get("comment", ""),
            status=ReviewStatus.PENDING,
        )
        return Response({"message": "Review submitted.", "id": rv.id}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsBranchAdmin], url_path="approve")
    @transaction.atomic
    def approve(self, request, pk=None):
        rv = self.get_object()
        s = ReviewModerateSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        rv.status = ReviewStatus.APPROVED
        rv.moderated_by = request.user
        rv.moderated_at = timezone.now()
        rv.moderation_note = s.validated_data.get("note", "")
        rv.save(update_fields=["status", "moderated_by", "moderated_at", "moderation_note", "updated_at"])
        return Response({"message": "Approved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsBranchAdmin], url_path="reject")
    @transaction.atomic
    def reject(self, request, pk=None):
        rv = self.get_object()
        s = ReviewModerateSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        rv.status = ReviewStatus.REJECTED
        rv.moderated_by = request.user
        rv.moderated_at = timezone.now()
        rv.moderation_note = s.validated_data.get("note", "")
        rv.save(update_fields=["status", "moderated_by", "moderated_at", "moderation_note", "updated_at"])
        return Response({"message": "Rejected."}, status=status.HTTP_200_OK)