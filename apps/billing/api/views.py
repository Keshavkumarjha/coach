from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.tenant import get_tenant_context
from apps.common.permissions import IsBranchAdmin, IsStudentOrParent
from apps.billing.models import PaymentSettings, FeeInvoice, PaymentTransaction, TxnStatus, InvoiceStatus

from apps.billing.api.serializers import (
    PaymentSettingsSerializer,
    FeeInvoiceSerializer,
    InvoiceGenerateSerializer,
    PaymentTransactionCreateSerializer,
    PaymentTransactionSerializer,
    TxnReviewSerializer,
)


class PaymentSettingsViewSet(ModelViewSet):
    """
    Admin sets bank/UPI/QR per branch.
    """
    serializer_class = PaymentSettingsSerializer
    permission_classes = [IsBranchAdmin]
    http_method_names = ["get", "post", "patch", "put"]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return PaymentSettings.objects.filter(organisation=ctx.organisation, branch=ctx.branch)

    def create(self, request, *args, **kwargs):
        """
        Create or update singleton (OneToOne with Branch).
        """
        ctx = get_tenant_context(request)
        obj = PaymentSettings.objects.filter(organisation=ctx.organisation, branch=ctx.branch).first()
        s = self.get_serializer(instance=obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        saved = s.save(organisation=ctx.organisation, branch=ctx.branch)
        return Response(PaymentSettingsSerializer(saved).data, status=status.HTTP_200_OK)


class FeeInvoiceViewSet(ModelViewSet):
    """
    Admin lists invoices + can bulk generate invoices.
    Students can list their own invoices (optional in future).
    """
    serializer_class = FeeInvoiceSerializer
    permission_classes = [IsBranchAdmin]
    http_method_names = ["get"]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return FeeInvoice.objects.select_related("student", "student__user", "batch").filter(
            organisation=ctx.organisation, branch=ctx.branch
        ).order_by("-period_year", "-period_month", "-created_at")

    @action(detail=False, methods=["post"], permission_classes=[IsBranchAdmin], url_path="generate")
    @transaction.atomic
    def generate(self, request):
        """
        POST /api/invoices/generate/
        """
        s = InvoiceGenerateSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        result = s.save()
        return Response(
            {"message": "Invoices generated.", **result},
            status=status.HTTP_200_OK,
        )


class PaymentTransactionViewSet(ModelViewSet):
    """
    - Admin: list all txns, approve/reject
    - Student: create txn (upload proof), list own txns (optional)
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post"]

    def get_permissions(self):
        if self.action in {"create", "my"}:
            return [IsStudentOrParent()]
        return [IsBranchAdmin()]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return PaymentTransaction.objects.select_related("student", "student__user", "invoice").filter(
            organisation=ctx.organisation, branch=ctx.branch
        ).order_by("-paid_at", "-created_at")

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentTransactionCreateSerializer
        return PaymentTransactionSerializer

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        txn = s.save()
        return Response(PaymentTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], permission_classes=[IsStudentOrParent], url_path="my")
    def my(self, request):
        """
        Student fetch own txns.
        GET /api/transactions/my/
        """
        ctx = get_tenant_context(request)
        student = getattr(request.user, "student_profile", None)
        if not student:
            return Response({"detail": "Student login required."}, status=status.HTTP_400_BAD_REQUEST)

        qs = PaymentTransaction.objects.select_related("invoice").filter(
            organisation=ctx.organisation, branch=ctx.branch, student=student
        ).order_by("-paid_at")[:200]

        return Response(PaymentTransactionSerializer(qs, many=True).data)

    @action(detail=True, methods=["post"], permission_classes=[IsBranchAdmin], url_path="approve")
    @transaction.atomic
    def approve(self, request, pk=None):
        """
        POST /api/transactions/{id}/approve/
        """
        ctx = get_tenant_context(request)
        txn = self.get_object()

        if txn.status != TxnStatus.PENDING:
            return Response({"detail": "Transaction is not pending."}, status=status.HTTP_400_BAD_REQUEST)

        s = TxnReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        txn.status = TxnStatus.APPROVED
        txn.reviewed_by = request.user
        txn.reviewed_at = timezone.now()
        txn.review_note = s.validated_data.get("note", "")
        txn.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

        # Update invoice status if linked
        if txn.invoice_id:
            inv = txn.invoice
            inv.status = InvoiceStatus.PAID
            inv.save(update_fields=["status", "updated_at"])

        return Response({"message": "Approved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsBranchAdmin], url_path="reject")
    @transaction.atomic
    def reject(self, request, pk=None):
        """
        POST /api/transactions/{id}/reject/
        """
        ctx = get_tenant_context(request)
        txn = self.get_object()

        if txn.status != TxnStatus.PENDING:
            return Response({"detail": "Transaction is not pending."}, status=status.HTTP_400_BAD_REQUEST)

        s = TxnReviewSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        txn.status = TxnStatus.REJECTED
        txn.reviewed_by = request.user
        txn.reviewed_at = timezone.now()
        txn.review_note = s.validated_data.get("note", "")
        txn.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_note", "updated_at"])

        return Response({"message": "Rejected."}, status=status.HTTP_200_OK)