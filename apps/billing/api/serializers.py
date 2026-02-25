from __future__ import annotations

from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.common.tenant import get_tenant_context
from apps.billing.models import (
    PaymentSettings,
    FeeInvoice,
    PaymentTransaction,
    InvoiceStatus,
    TxnStatus,
    PaymentMode,
)
from apps.academics.models import StudentProfile, BatchEnrollment, EnrollmentStatus


class PaymentSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentSettings
        fields = [
            "id",
            "account_holder_name",
            "bank_name",
            "account_number",
            "ifsc_code",
            "upi_id",
            "upi_qr_image",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class FeeInvoiceSerializer(serializers.ModelSerializer):
    student_public_id = serializers.CharField(source="student.public_id", read_only=True)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    batch_name = serializers.CharField(source="batch.name", read_only=True)

    class Meta:
        model = FeeInvoice
        fields = [
            "public_id",
            "student_public_id",
            "student_name",
            "batch_name",
            "period_year",
            "period_month",
            "due_date",
            "amount",
            "status",
            "created_at",
        ]
        read_only_fields = ["public_id", "created_at", "student_public_id", "student_name", "batch_name"]


class InvoiceGenerateSerializer(serializers.Serializer):
    """
    Admin bulk generate invoices for a branch for given month.
    You can filter by batch_id.

    payload:
    {
      "period_year": 2026,
      "period_month": 2,
      "due_date": "2026-02-10",
      "amount": "1200.00",
      "batch_id": 12 (optional)
    }
    """
    period_year = serializers.IntegerField()
    period_month = serializers.IntegerField(min_value=1, max_value=12)
    due_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    batch_id = serializers.IntegerField(required=False)

    def validate_amount(self, v):
        if v <= 0:
            raise serializers.ValidationError("Amount must be > 0.")
        return v

    @transaction.atomic
    def create(self, vd):
        request = self.context["request"]
        ctx = get_tenant_context(request)

        qs_students = StudentProfile.objects.filter(
            organisation=ctx.organisation,
            branch=ctx.branch,
            is_active_for_login=True,
        ).select_related("user")

        batch_id = vd.get("batch_id")
        batch = None
        if batch_id:
            # Only students enrolled in this batch
            enrolled_student_ids = BatchEnrollment.objects.filter(
                batch_id=batch_id,
                status=EnrollmentStatus.ACTIVE,
                batch__organisation=ctx.organisation,
                batch__branch=ctx.branch,
            ).values_list("student_id", flat=True)
            qs_students = qs_students.filter(id__in=enrolled_student_ids)
            from apps.academics.models import Batch
            batch = Batch.objects.filter(id=batch_id, organisation=ctx.organisation, branch=ctx.branch).first()
            if not batch:
                raise serializers.ValidationError({"batch_id": "Invalid batch for this branch."})

        created = 0
        updated = 0

        for st in qs_students.iterator(chunk_size=1000):
            inv, was_created = FeeInvoice.objects.update_or_create(
                student=st,
                period_year=vd["period_year"],
                period_month=vd["period_month"],
                defaults={
                    "organisation": ctx.organisation,
                    "branch": ctx.branch,
                    "batch": batch,
                    "due_date": vd["due_date"],
                    "amount": vd["amount"],
                    "status": InvoiceStatus.DUE,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return {"created": created, "updated": updated}


class PaymentTransactionCreateSerializer(serializers.ModelSerializer):
    """
    Student/Parent uploads payment proof. Creates PENDING transaction.
    """
    invoice_public_id = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            "public_id",
            "invoice_public_id",
            "mode",
            "amount",
            "paid_at",
            "reference_no",
            "proof_image",
        ]
        read_only_fields = ["public_id"]

    def validate(self, attrs):
        if attrs.get("amount") is None or attrs["amount"] <= Decimal("0.00"):
            raise serializers.ValidationError({"amount": "Amount must be > 0."})
        if attrs.get("mode") not in PaymentMode.values:
            raise serializers.ValidationError({"mode": "Invalid mode."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        ctx = get_tenant_context(request)

        # Resolve student
        student = getattr(request.user, "student_profile", None)
        if not student:
            # parent paying for linked student can be added later,
            # for now require student login for payment
            raise serializers.ValidationError({"detail": "Student login required to pay."})

        invoice = None
        inv_pid = (validated_data.get("invoice_public_id") or "").strip()
        if inv_pid:
            invoice = FeeInvoice.objects.filter(
                public_id=inv_pid,
                organisation=ctx.organisation,
                branch=ctx.branch,
                student=student,
            ).first()
            if not invoice:
                raise serializers.ValidationError({"invoice_public_id": "Invalid invoice."})

        txn = PaymentTransaction.objects.create(
            organisation=ctx.organisation,
            branch=ctx.branch,
            invoice=invoice,
            student=student,
            created_by=request.user,
            mode=validated_data["mode"],
            amount=validated_data["amount"],
            paid_at=validated_data.get("paid_at") or timezone.now(),
            reference_no=validated_data.get("reference_no", ""),
            proof_image=validated_data.get("proof_image"),
            status=TxnStatus.PENDING,
        )
        return txn


class PaymentTransactionSerializer(serializers.ModelSerializer):
    student_public_id = serializers.CharField(source="student.public_id", read_only=True)
    student_name = serializers.CharField(source="student.user.full_name", read_only=True)
    invoice_public_id = serializers.CharField(source="invoice.public_id", read_only=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            "public_id",
            "invoice_public_id",
            "student_public_id",
            "student_name",
            "mode",
            "amount",
            "paid_at",
            "reference_no",
            "proof_image",
            "status",
            "review_note",
            "created_at",
        ]
        read_only_fields = fields


class TxnReviewSerializer(serializers.Serializer):
    """
    Admin approves/rejects a txn.
    payload:
    { "note": "ok" }
    """
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)