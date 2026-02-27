"""
billing/api/views_subscription.py  — COMPLETE FIXED VERSION

SaaS subscription plan management.

Endpoints
─────────
GET /api/subscription/         Current org's subscription + limits
GET /api/subscription/plans/   All available public plans (pricing page)
GET /api/subscription/usage/   Current usage counts vs plan limits  ← FIX #6 (new)
"""
from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsBranchAdmin
from apps.billing.models import SubscriptionPlan, OrganisationSubscription


# ─── Serializers ─────────────────────────────────────────────────────────────

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "code",
            "name",
            "price_monthly_inr",
            "student_limit",
            "branch_limit",
            "teacher_limit",
            "feature_whatsapp_marketing",
            "feature_id_cards",
            "feature_reviews",
            "feature_tests",
            "feature_geo_attendance",
        ]


class OrganisationSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    days_remaining = serializers.SerializerMethodField()

    class Meta:
        model = OrganisationSubscription
        fields = [
            "status",
            "plan",
            "started_on",
            "expires_on",
            "trial_ends_on",
            "days_remaining",
        ]

    def get_days_remaining(self, obj) -> int | None:
        from django.utils import timezone
        today = timezone.localdate()
        if obj.expires_on:
            delta = (obj.expires_on - today).days
            return max(delta, 0)
        return None


# ─── Views ────────────────────────────────────────────────────────────────────

class SubscriptionDetailView(APIView):
    """
    GET /api/subscription/

    Returns the current organisation's active subscription, including plan limits
    and feature flags. Used for feature-gating on the frontend.

    Permission: IsBranchAdmin
    """
    permission_classes = [IsBranchAdmin]

    def get(self, request):
        from apps.common.tenant import get_tenant_context
        ctx = get_tenant_context(request)

        sub = (
            OrganisationSubscription.objects
            .select_related("plan")
            .filter(organisation=ctx.organisation)
            .first()
        )
        if not sub:
            return Response(
                {"detail": "No subscription found for this organisation."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            OrganisationSubscriptionSerializer(sub).data,
            status=status.HTTP_200_OK,
        )


class SubscriptionPlanListView(APIView):
    """
    GET /api/subscription/plans/

    Public list of all available subscription plans and pricing.
    Used on the pricing/upgrade page.

    Permission: IsAuthenticated
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_public=True).order_by("price_monthly_inr")
        return Response(
            SubscriptionPlanSerializer(plans, many=True).data,
            status=status.HTTP_200_OK,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# FIX #6 — SubscriptionUsageView: new endpoint GET /api/subscription/usage/
#
# PROBLEM: /api/subscription/ returned plan limits (student_limit: 200) but
#          NOT current usage (how many students are actually active). The
#          billing/upgrade page needed both numbers to render the usage bars,
#          so without this the frontend showed "—/200" for every metric.
#
# FIX:     New dedicated view that queries actual counts at both org level
#          (for per-org limits like branch count) and branch level (for per-branch
#          usage). Returns a structured _usage dict with used/limit/pct for each
#          resource so the frontend can render progress bars directly.
# ═══════════════════════════════════════════════════════════════════════════════
class SubscriptionUsageView(APIView):
    """
    GET /api/subscription/usage/

    Returns current usage counts vs plan limits for the requesting org/branch.
    Designed to power usage progress bars on the billing/upgrade page.

    Permission: IsBranchAdmin

    Response:
    {
      "plan_code": "GROWTH",
      "org_level": {
        "branches":       { "used": 3,   "limit": 5,   "pct": 60.0 },
        "students_total": { "used": 147, "limit": 200, "pct": 73.5 },
        "teachers_total": { "used": 12,  "limit": null, "pct": null }
      },
      "this_branch": {
        "students": { "used": 55,  "limit": 200, "pct": 27.5 },
        "teachers": { "used": 4,   "limit": null, "pct": null }
      }
    }

    Notes:
      - limit: null means the plan has no cap on that resource
      - pct: null when limit is null (no percentage makes sense)
      - org_level.students_total is the sum across all branches
      - this_branch counts are scoped to the X-Branch header
    """
    permission_classes = [IsBranchAdmin]

    @staticmethod
    def _slot(used: int, limit: int | None) -> dict:
        """Build { used, limit, pct } — pct is null when there's no limit."""
        pct = round(used / limit * 100, 1) if limit else None
        return {"used": used, "limit": limit, "pct": pct}

    def get(self, request):
        from apps.common.tenant import get_tenant_context
        from apps.academics.models import StudentProfile, TeacherProfile
        from apps.orgs.models import Branch

        ctx = get_tenant_context(request)

        # ── Resolve plan limits ───────────────────────────────────────────────
        sub = (
            OrganisationSubscription.objects
            .select_related("plan")
            .filter(organisation=ctx.organisation)
            .first()
        )
        plan = sub.plan if sub else None
        student_limit = plan.student_limit if plan else None
        branch_limit  = plan.branch_limit  if plan else None
        teacher_limit = plan.teacher_limit if plan else None

        # ── Org-level counts ──────────────────────────────────────────────────
        branch_count = Branch.objects.filter(
            organisation=ctx.organisation,
        ).count()

        org_students = StudentProfile.objects.filter(
            organisation=ctx.organisation,
            is_active_for_login=True,
        ).count()

        org_teachers = TeacherProfile.objects.filter(
            organisation=ctx.organisation,
            is_active_for_login=True,
        ).count()

        # ── Branch-level counts ───────────────────────────────────────────────
        br_students = StudentProfile.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
            is_active_for_login=True,
        ).count()

        br_teachers = TeacherProfile.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
            is_active_for_login=True,
        ).count()

        return Response(
            {
                "plan_code": plan.code if plan else None,
                "org_level": {
                    "branches":       self._slot(branch_count, branch_limit),
                    "students_total": self._slot(org_students, student_limit),
                    "teachers_total": self._slot(org_teachers, teacher_limit),
                },
                "this_branch": {
                    "students": self._slot(br_students, student_limit),
                    "teachers": self._slot(br_teachers, teacher_limit),
                },
            },
            status=status.HTTP_200_OK,
        )
