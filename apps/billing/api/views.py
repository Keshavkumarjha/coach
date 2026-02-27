"""
billing/api/views.py  — COMPLETE VERSION

All billing endpoints:
  GET/POST      /api/payment-settings/
  GET/PATCH     /api/payment-settings/{id}/

  GET/POST      /api/invoices/
  GET           /api/invoices/{id}/
  POST          /api/invoices/generate/          Bulk generate invoices for a batch+period
  GET           /api/invoices/my/                Student's own invoices (IsStudentOrParent)

  GET/POST      /api/transactions/
  GET           /api/transactions/{id}/
  POST          /api/transactions/{id}/approve/
  POST          /api/transactions/{id}/reject/
"""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.mixins import (
    TenantViewSet,
    StatusFilterMixin,
    ApproveRejectMixin,
)
from apps.common.permissions import IsBranchAdmin, IsStudentOrParent
from apps.billing.api.serializers import (
    PaymentSettingsSerializer,
    FeeInvoiceSerializer,
    PaymentTransactionSerializer,
    GenerateInvoicesSerializer,
)
from apps.billing.models import (
    PaymentSettings,
    FeeInvoice,
    InvoiceStatus,
    PaymentTransaction,
    TxnStatus,
)
from apps.academics.models import StudentProfile


# ─────────────────────────────────────────────────────────────────────────────
# Payment Settings
# ─────────────────────────────────────────────────────────────────────────────

class PaymentSettingsViewSet(TenantViewSet):
    """
    Bank account / UPI settings per branch.
    Permission: IsBranchAdmin
    """
    serializer_class = PaymentSettingsSerializer
    permission_classes = [IsBranchAdmin]
    queryset = PaymentSettings.objects.all()
    ordering = ["-created_at"]


# ─────────────────────────────────────────────────────────────────────────────
# Fee Invoices
# ─────────────────────────────────────────────────────────────────────────────

class FeeInvoiceViewSet(StatusFilterMixin, TenantViewSet):
    """
    Fee invoice management.

    Admin endpoints:
        GET    /api/invoices/              List (filter ?status=, ?batch_id=)
        GET    /api/invoices/{id}/
        POST   /api/invoices/generate/    Bulk-create invoices for batch + period

    Student endpoint:
        GET    /api/invoices/my/          Student's own invoices

    Permission:
        Admin actions: IsBranchAdmin
        my/ action:    IsStudentOrParent

    Query params:
        ?status=DUE | PAID | PARTIAL | CANCELLED
        ?batch_id=<int>
        ?year=<int>
        ?month=<int>
    """
    serializer_class = FeeInvoiceSerializer
    permission_classes = [IsBranchAdmin]
    queryset = FeeInvoice.objects.select_related("student", "student__user", "batch").all()
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action == "my":
            return [IsStudentOrParent()]
        return [IsBranchAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        batch_id = self.request.query_params.get("batch_id")
        year     = self.request.query_params.get("year")
        month    = self.request.query_params.get("month")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        if year:
            qs = qs.filter(period_year=year)
        if month:
            qs = qs.filter(period_month=month)
        return qs

    @action(detail=False, methods=["post"], url_path="generate", permission_classes=[IsBranchAdmin])
    @transaction.atomic
    def generate(self, request):
        """
        POST /api/invoices/generate/

        Bulk-generates invoices for all active students in a batch for a given period.

        Body:
            batch_id      int   required
            period_year   int   required
            period_month  int   required  (1–12)
            due_date      date  required
            amount        str   required  (decimal string)
        """
        serializer = GenerateInvoicesSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="my")
    def my(self, request):
        """
        GET /api/invoices/my/

        Returns the current student's own invoices.
        Supports ?status= / ?year= / ?month= filters.
        """
        ctx = self.get_tenant()

        student = StudentProfile.objects.filter(
            user=request.user,
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).first()
        if not student:
            return Response(
                {"detail": "Student profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        qs = FeeInvoice.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
            student=student,
        ).select_related("batch").order_by("-period_year", "-period_month")

        # Filters
        s     = request.query_params.get("status")
        year  = request.query_params.get("year")
        month = request.query_params.get("month")
        if s:
            qs = qs.filter(status=s.upper())
        if year:
            qs = qs.filter(period_year=year)
        if month:
            qs = qs.filter(period_month=month)

        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(FeeInvoiceSerializer(page, many=True).data)
        return Response(FeeInvoiceSerializer(qs, many=True).data)


# ─────────────────────────────────────────────────────────────────────────────
# Payment Transactions
# ─────────────────────────────────────────────────────────────────────────────

class PaymentTransactionViewSet(StatusFilterMixin, ApproveRejectMixin, TenantViewSet):
    """
    Payment proof upload + admin approve/reject.

    GET/POST    /api/transactions/
    POST        /api/transactions/{id}/approve/
    POST        /api/transactions/{id}/reject/

    Permission:
        list/retrieve:   IsBranchAdmin
        create:          IsStudentOrParent (student uploads proof)
        approve/reject:  IsBranchAdmin
    """
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsBranchAdmin]
    queryset = PaymentTransaction.objects.select_related(
        "student", "student__user", "invoice", "invoice__batch"
    ).all()
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action == "create":
            return [IsStudentOrParent()]
        return [IsBranchAdmin()]

    def perform_create(self, serializer):
        ctx = self.get_tenant()
        serializer.save(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=self.request.user,
        )

    @transaction.atomic
    def _do_approve(self, request, txn: PaymentTransaction) -> dict:
        if txn.status != TxnStatus.PENDING:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "Transaction is not pending."})

        note = (request.data.get("note") or "").strip()[:200]

        txn.status      = TxnStatus.APPROVED
        txn.reviewed_by = request.user
        txn.reviewed_at = timezone.now()
        txn.review_note = note
        txn.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

        # Mark related invoice as PAID if amount covers it
        if txn.invoice:
            total_approved = (
                PaymentTransaction.objects
                .filter(invoice=txn.invoice, status=TxnStatus.APPROVED)
                .aggregate(t=__import__("django.db.models", fromlist=["Sum"]).Sum("amount"))["t"]
                or Decimal("0")
            )
            if total_approved >= txn.invoice.amount:
                txn.invoice.status = InvoiceStatus.PAID
                txn.invoice.save(update_fields=["status", "updated_at"])
            elif total_approved > 0:
                txn.invoice.status = InvoiceStatus.PARTIAL
                txn.invoice.save(update_fields=["status", "updated_at"])

        return {"message": "Payment approved.", "status": TxnStatus.APPROVED}

    @transaction.atomic
    def _do_reject(self, request, txn: PaymentTransaction) -> dict:
        if txn.status != TxnStatus.PENDING:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "Transaction is not pending."})

        note = (request.data.get("note") or "").strip()[:200]

        txn.status      = TxnStatus.REJECTED
        txn.reviewed_by = request.user
        txn.reviewed_at = timezone.now()
        txn.review_note = note
        txn.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

        return {"message": "Payment rejected.", "status": TxnStatus.REJECTED}
