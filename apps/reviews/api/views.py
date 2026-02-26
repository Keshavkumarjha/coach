"""
reviews/api/views.py

Public review submission and admin moderation.

Endpoints
─────────
GET             /api/reviews/                 Admin: list all reviews
POST            /api/reviews/public-submit/   Public: submit a review
POST            /api/reviews/{id}/approve/    Admin: approve
POST            /api/reviews/{id}/reject/     Admin: reject
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.common.mixins import TenantViewSet, StatusFilterMixin, ApproveRejectMixin
from apps.common.permissions import IsBranchAdmin
from apps.orgs.models import Organisation, Branch
from apps.reviews.models import Review, ReviewStatus
from apps.reviews.api.serializers import ReviewSerializer, ReviewModerateSerializer


class ReviewViewSet(StatusFilterMixin, ApproveRejectMixin, TenantViewSet):
    """
    Reviews scoped to the current branch.

    Permissions:
        list / retrieve               → IsBranchAdmin
        public-submit                 → AllowAny
        approve / reject              → IsBranchAdmin  (from ApproveRejectMixin)

    Query params:
        ?status=PENDING | APPROVED | REJECTED
        ?rating=<1-5>

    Public submit:
        POST /api/reviews/public-submit/?org=ORG-..&branch=BR-..
        Body: { author_name, author_mobile, rating, title, comment }
        No authentication required — org/branch passed as query params or headers.
    """
    serializer_class = ReviewSerializer
    permission_classes = [IsBranchAdmin]
    queryset = Review.objects.all()
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "delete"]

    def get_queryset(self):
        qs = super().get_queryset()
        rating = self.request.query_params.get("rating")
        if rating:
            qs = qs.filter(rating=rating)
        return qs

    # Public submit — no authentication needed
    @action(
        detail=False,
        methods=["post"],
        permission_classes=[AllowAny],
        url_path="public-submit",
    )
    def public_submit(self, request):
        """
        POST /api/reviews/public-submit/
        Headers or query params: X-Org, X-Branch (or ?org=..&branch=..)
        """
        org_pid = (
            request.query_params.get("org")
            or request.headers.get("X-Org")
        )
        br_pid = (
            request.query_params.get("branch")
            or request.headers.get("X-Branch")
        )
        if not org_pid or not br_pid:
            raise ValidationError({"detail": "org and branch are required."})

        org = Organisation.objects.filter(public_id=org_pid).first()
        if not org:
            raise ValidationError({"detail": "Invalid organisation."})

        branch = Branch.objects.filter(public_id=br_pid, organisation=org).first()
        if not branch:
            raise ValidationError({"detail": "Invalid branch."})

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = Review.objects.create(
            organisation=org,
            branch=branch,
            author_name=serializer.validated_data.get("author_name", ""),
            author_mobile=serializer.validated_data.get("author_mobile", ""),
            rating=serializer.validated_data["rating"],
            title=serializer.validated_data.get("title", ""),
            comment=serializer.validated_data.get("comment", ""),
            status=ReviewStatus.PENDING,
        )
        return Response(
            {"message": "Review submitted.", "id": review.id},
            status=status.HTTP_201_CREATED,
        )

    # ── ApproveRejectMixin hooks ──────────────────────────────────────────────

    @transaction.atomic
    def _do_approve(self, request, review: Review) -> dict:
        serializer = ReviewModerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review.status = ReviewStatus.APPROVED
        review.moderated_by = request.user
        review.moderated_at = timezone.now()
        review.moderation_note = serializer.validated_data.get("note", "")
        review.save(update_fields=[
            "status", "moderated_by", "moderated_at", "moderation_note", "updated_at"
        ])
        return {"message": "Review approved."}

    @transaction.atomic
    def _do_reject(self, request, review: Review) -> dict:
        serializer = ReviewModerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review.status = ReviewStatus.REJECTED
        review.moderated_by = request.user
        review.moderated_at = timezone.now()
        review.moderation_note = serializer.validated_data.get("note", "")
        review.save(update_fields=[
            "status", "moderated_by", "moderated_at", "moderation_note", "updated_at"
        ])
        return {"message": "Review rejected."}
