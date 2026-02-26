"""
apps/common/mixins.py

Shared base classes used by every ViewSet across the entire project.
Every app imports from here — never duplicating tenant-scoping logic.

Class hierarchy
───────────────
StandardPagination
TenantMixin                 → resolves & caches (org, branch) from headers
  TenantFilterMixin         → scopes get_queryset() to org + branch
  TenantCreateMixin         → injects org+branch (+ optional created_by) on save
    TenantViewSet           → TenantFilterMixin + TenantCreateMixin + ModelViewSet
      (all app ViewSets inherit from this)

Standalone mixins (compose on top of TenantViewSet)
───────────────────────────────────────────────────
StatusFilterMixin           → ?status=
BatchFilterMixin            → ?batch_id=
DateRangeFilterMixin        → ?from_date= / ?to_date=
SearchFilterMixin           → ?search=
ApproveRejectMixin          → approve / reject @actions with hook methods
BulkActionMixin             → generic bulk POST helper
"""
from __future__ import annotations

from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.tenant import get_tenant_context


# ─────────────────────────────────────────────────────────────────────────────
# Pagination
# ─────────────────────────────────────────────────────────────────────────────

class StandardPagination(PageNumberPagination):
    """
    20 results per page. Client may override with ?page_size=N (max 200).

    Response envelope:
        { "count": 123, "next": "…?page=3", "previous": "…?page=1", "results": [...] }
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200


# ─────────────────────────────────────────────────────────────────────────────
# Tenant resolution
# ─────────────────────────────────────────────────────────────────────────────

class TenantMixin:
    """
    Resolves and caches the TenantContext (org + branch + membership)
    from X-Org / X-Branch headers on the first call.

    Usage in any method:
        ctx = self.get_tenant()
        ctx.organisation, ctx.branch, ctx.membership
    """

    def get_tenant(self):
        if not hasattr(self, "_tenant_ctx"):
            self._tenant_ctx = get_tenant_context(self.request)
        return self._tenant_ctx


# ─────────────────────────────────────────────────────────────────────────────
# Queryset scoping — automatically applies org + branch filter
# ─────────────────────────────────────────────────────────────────────────────

class TenantFilterMixin(TenantMixin):
    """
    Overrides get_queryset() to automatically scope to current org + branch.

    Subclasses MUST set class-level `queryset`. Additional static filters
    can be added via `tenant_filter_fields`:
        tenant_filter_fields = {"is_active_for_login": True}
    """
    tenant_filter_fields: dict = {}

    def get_queryset(self):
        ctx = self.get_tenant()
        return super().get_queryset().filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
            **self.tenant_filter_fields,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Auto-inject org + branch on create
# ─────────────────────────────────────────────────────────────────────────────

class TenantCreateMixin(TenantMixin):
    """
    Injects `organisation` + `branch` into every serializer.save() call.
    Set `inject_created_by = True` on viewsets whose model has a `created_by` FK.
    """
    inject_created_by: bool = False

    def perform_create(self, serializer):
        ctx = self.get_tenant()
        extra = {
            "organisation": ctx.organisation,
            "branch": ctx.branch,
        }
        if self.inject_created_by:
            extra["created_by"] = self.request.user
        serializer.save(**extra)


# ─────────────────────────────────────────────────────────────────────────────
# Combined base ViewSet — the one class every app ViewSet inherits
# ─────────────────────────────────────────────────────────────────────────────

class TenantViewSet(TenantFilterMixin, TenantCreateMixin, ModelViewSet):
    """
    Full-featured tenant-scoped ModelViewSet with pagination.

    Minimal subclass example:
        class BatchViewSet(TenantViewSet):
            serializer_class = BatchSerializer
            permission_classes = [IsBranchAdmin]
            queryset = Batch.objects.all()
            ordering = ["-created_at"]
    """
    pagination_class = StandardPagination
    ordering: list[str] = ["-created_at"]

    def get_queryset(self):
        ctx = self.get_tenant()
        qs = self.queryset.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
            **self.tenant_filter_fields,
        )
        if self.ordering:
            qs = qs.order_by(*self.ordering)
        return qs


# ─────────────────────────────────────────────────────────────────────────────
# Query-param filter mixins  (stack on top of TenantViewSet)
# ─────────────────────────────────────────────────────────────────────────────

class StatusFilterMixin:
    """
    Adds ?status=ACTIVE filter.
    Override `status_filter_field` to change the DB field (default: "status").
    Example: GET /api/invoices/?status=DUE
    """
    status_filter_field: str = "status"

    def get_queryset(self):
        qs = super().get_queryset()
        val = self.request.query_params.get("status")
        if val:
            qs = qs.filter(**{self.status_filter_field: val.upper()})
        return qs


class BatchFilterMixin:
    """
    Adds ?batch_id=<int> filter.
    Example: GET /api/attendance/?batch_id=5
    """
    def get_queryset(self):
        qs = super().get_queryset()
        batch_id = self.request.query_params.get("batch_id")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        return qs


class DateRangeFilterMixin:
    """
    Adds ?from_date=YYYY-MM-DD and ?to_date=YYYY-MM-DD.
    Override `date_filter_field` to pick the timestamp field.
    Default: "created_at__date"
    """
    date_filter_field: str = "created_at__date"

    def get_queryset(self):
        qs = super().get_queryset()
        from_date = self.request.query_params.get("from_date")
        to_date = self.request.query_params.get("to_date")
        if from_date:
            qs = qs.filter(**{f"{self.date_filter_field}__gte": from_date})
        if to_date:
            qs = qs.filter(**{f"{self.date_filter_field}__lte": to_date})
        return qs


class SearchFilterMixin:
    """
    Adds ?search=<term> filter across declared fields.

    Subclass must declare:
        search_fields = ["user__full_name__icontains", "admission_no__icontains"]
    """
    search_fields: list[str] = []

    def get_queryset(self):
        qs = super().get_queryset()
        term = self.request.query_params.get("search", "").strip()
        if term and self.search_fields:
            q = Q()
            for field in self.search_fields:
                q |= Q(**{field: term})
            qs = qs.filter(q)
        return qs


# ─────────────────────────────────────────────────────────────────────────────
# Approve / Reject mixin
# ─────────────────────────────────────────────────────────────────────────────

class ApproveRejectMixin:
    """
    Adds `approve` and `reject` @actions to any ViewSet.

    Subclass must implement:
        _do_approve(self, request, obj) -> dict
        _do_reject(self, request, obj)  -> dict

    Both should raise serializers.ValidationError on business-rule failure.
    """
    approve_permission_classes: list = []
    reject_permission_classes: list = []

    def _get_action_permissions(self, action_name: str):
        if action_name == "approve" and self.approve_permission_classes:
            return [p() for p in self.approve_permission_classes]
        if action_name == "reject" and self.reject_permission_classes:
            return [p() for p in self.reject_permission_classes]
        return self.get_permissions()

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        for perm in self._get_action_permissions("approve"):
            if not perm.has_permission(request, self):
                return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj = self.get_object()
        result = self._do_approve(request, obj)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        for perm in self._get_action_permissions("reject"):
            if not perm.has_permission(request, self):
                return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        obj = self.get_object()
        result = self._do_reject(request, obj)
        return Response(result, status=status.HTTP_200_OK)

    def _do_approve(self, request, obj) -> dict:
        raise NotImplementedError(f"{self.__class__.__name__} must implement _do_approve()")

    def _do_reject(self, request, obj) -> dict:
        raise NotImplementedError(f"{self.__class__.__name__} must implement _do_reject()")


# ─────────────────────────────────────────────────────────────────────────────
# Bulk action mixin
# ─────────────────────────────────────────────────────────────────────────────

class BulkActionMixin:
    """
    Helper for POSTing to a list-level action and running a serializer on it.

    Usage in a ViewSet:
        @action(detail=False, methods=["post"], url_path="bulk-mark")
        def bulk_mark(self, request):
            return self.run_bulk_action(request, BulkMarkSerializer)
    """
    def run_bulk_action(self, request, serializer_class, **extra_context):
        ctx = {"request": request, **extra_context}
        s = serializer_class(data=request.data, context=ctx)
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response(result, status=status.HTTP_200_OK)
