"""
billing/api/views.py

All billing-related ViewSets.

Endpoints
─────────
Payment Settings (Admin)
  GET/POST/PATCH  /api/payment-settings/        Upsert branch bank/UPI details

Fee Invoices (Admin)
  GET             /api/invoices/                List invoices
  POST            /api/invoices/generate/       Bulk-generate invoices for a month

Payment Transactions
  GET             /api/transactions/            Admin: list all transactions
  POST            /api/transactions/            Student: upload payment proof
  GET             /api/transactions/my/         Student: view own transactions
  POST            /api/transactions/{id}/approve/  Admin: approve payment
  POST            /api/transactions/{id}/reject/   Admin: reject payment
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.common.mixins import (
    TenantViewSet,
    ApproveRejectMixin,
    StatusFilterMixin,
    DateRangeFilterMixin,
)
from apps.common.permissions import IsBranchAdmin, IsStudentOrParent
from apps.billing.models import (
    FeeInvoice,
    InvoiceStatus,
    PaymentSettings,
    PaymentTransaction,
    TxnStatus,
)
from apps.billing.api.serializers import (
    FeeInvoiceSerializer,
    InvoiceGenerateSerializer,
    PaymentSettingsSerializer,
    PaymentTransactionCreateSerializer,
    PaymentTransactionSerializer,
    TxnReviewSerializer,
)


class PaymentSettingsViewSet(TenantViewSet):
    """
    Singleton per branch: create or update bank/UPI/QR settings.

    GET  /api/payment-settings/    Returns current settings (or empty list)
    POST /api/payment-settings/    Upsert (create if missing, update if exists)
    PATCH /api/payment-settings/{id}/
    """
    serializer_class = PaymentSettingsSerializer
    permission_classes = [IsBranchAdmin]
    queryset = PaymentSettings.objects.all()
    http_method_names = ["get", "post", "patch", "put"]

    def create(self, request, *args, **kwargs):
        ctx = self.get_tenant()
        existing = PaymentSettings.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).first()
        serializer = PaymentSettingsSerializer(
            instance=existing,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        saved = serializer.save(
            organisation=ctx.organisation,
            branch=ctx.branch,
        )
        return Response(PaymentSettingsSerializer(saved).data, status=status.HTTP_200_OK)


class FeeInvoiceViewSet(StatusFilterMixin, TenantViewSet):
    """
    Admin-only: list invoices and bulk-generate for a period.

    Query params:
        ?status=DUE | PAID | PARTIAL | CANCELLED
        ?batch_id=<int>

    Custom action:
        POST /api/invoices/generate/   Body: { period_year, period_month, due_date, amount, batch_id? }
    """
    serializer_class = FeeInvoiceSerializer
    permission_classes = [IsBranchAdmin]
    queryset = FeeInvoice.objects.select_related("student", "student__user", "batch").all()
    ordering = ["-period_year", "-period_month", "-created_at"]
    http_method_names = ["get", "post"]

    def get_queryset(self):
        qs = super().get_queryset()
        batch_id = self.request.query_params.get("batch_id")
        if batch_id:
            qs = qs.filter(batch_id=batch_id)
        return qs

    @action(detail=False, methods=["post"], url_path="generate")
    @transaction.atomic
    def generate(self, request):
        """
        POST /api/invoices/generate/
        Bulk-generates invoices for every active student in a branch (or batch).
        """
        serializer = InvoiceGenerateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {"message": "Invoices generated.", **result},
            status=status.HTTP_200_OK,
        )


class PaymentTransactionViewSet(
    ApproveRejectMixin,
    DateRangeFilterMixin,
    StatusFilterMixin,
    TenantViewSet,
):
    """
    Student submits payment proof → admin approves/rejects.

    Permissions:
        create, my  → IsStudentOrParent
        all others  → IsBranchAdmin

    Query params (admin list):
        ?status=PENDING | APPROVED | REJECTED
        ?from_date=YYYY-MM-DD
        ?to_date=YYYY-MM-DD

    Custom actions:
        GET  /api/transactions/my/           Student's own transactions
        POST /api/transactions/{id}/approve/ Approve + mark invoice PAID
        POST /api/transactions/{id}/reject/  Reject

    date_filter_field = "paid_at__date" (override from DateRangeFilterMixin)
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    queryset = PaymentTransaction.objects.select_related(
        "student", "student__user", "invoice", "invoice__batch",
    ).all()
    ordering = ["-paid_at", "-created_at"]
    http_method_names = ["get", "post"]
    date_filter_field = "paid_at__date"

    def get_permissions(self):
        if self.action in {"create", "my"}:
            return [IsStudentOrParent()]
        return [IsBranchAdmin()]

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentTransactionCreateSerializer
        return PaymentTransactionSerializer

    def create(self, request, *args, **kwargs):
        serializer = PaymentTransactionCreateSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        txn = serializer.save()
        return Response(
            PaymentTransactionSerializer(txn).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="my")
    def my(self, request):
        """
        GET /api/transactions/my/
        Returns the authenticated student's own payment history.
        """
        ctx = self.get_tenant()
        student = getattr(request.user, "student_profile", None)
        if not student:
            return Response(
                {"detail": "Student login required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = (
            PaymentTransaction.objects
            .select_related("invoice", "invoice__batch")
            .filter(
                organisation=ctx.organisation,
                branch=ctx.branch,
                student=student,
            )
            .order_by("-paid_at")
        )
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(PaymentTransactionSerializer(page, many=True).data)
        return Response(PaymentTransactionSerializer(qs, many=True).data)

    # ── ApproveRejectMixin hooks ──────────────────────────────────────────────

    def _do_approve(self, request, txn: PaymentTransaction) -> dict:
        if txn.status != TxnStatus.PENDING:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "Transaction is not pending."})

        note_serializer = TxnReviewSerializer(data=request.data)
        note_serializer.is_valid(raise_exception=True)

        txn.status = TxnStatus.APPROVED
        txn.reviewed_by = request.user
        txn.reviewed_at = timezone.now()
        txn.review_note = note_serializer.validated_data.get("note", "")
        txn.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

        if txn.invoice_id:
            FeeInvoice.objects.filter(pk=txn.invoice_id).update(status=InvoiceStatus.PAID)

        return {"message": "Approved.", "public_id": txn.public_id}

    def _do_reject(self, request, txn: PaymentTransaction) -> dict:
        if txn.status != TxnStatus.PENDING:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "Transaction is not pending."})

        note_serializer = TxnReviewSerializer(data=request.data)
        note_serializer.is_valid(raise_exception=True)

        txn.status = TxnStatus.REJECTED
        txn.reviewed_by = request.user
        txn.reviewed_at = timezone.now()
        txn.review_note = note_serializer.validated_data.get("note", "")
        txn.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

        return {"message": "Rejected.", "public_id": txn.public_id}
