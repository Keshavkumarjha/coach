"""
billing/api/serializers.py  — COMPLETE VERSION
"""
from __future__ import annotations

from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from apps.billing.models import (
    PaymentSettings,
    FeePlan,
    FeeInvoice,
    InvoiceStatus,
    PaymentTransaction,
    TxnStatus,
)
from apps.academics.models import Batch, BatchEnrollment, EnrollmentStatus
from apps.common.tenant import get_tenant_context


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
    student_name    = serializers.CharField(source="student.user.full_name", read_only=True)
    student_mobile  = serializers.CharField(source="student.user.mobile",    read_only=True)
    student_pub_id  = serializers.CharField(source="student.public_id",      read_only=True)
    batch_name      = serializers.CharField(source="batch.name",             read_only=True, allow_null=True)

    class Meta:
        model = FeeInvoice
        fields = [
            "id",
            "public_id",
            "student",
            "student_name",
            "student_mobile",
            "student_pub_id",
            "batch",
            "batch_name",
            "period_year",
            "period_month",
            "due_date",
            "amount",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "public_id", "created_at", "updated_at",
            "student_name", "student_mobile", "student_pub_id", "batch_name",
        ]


class PaymentTransactionSerializer(serializers.ModelSerializer):
    student_name    = serializers.CharField(source="student.user.full_name", read_only=True)
    student_pub_id  = serializers.CharField(source="student.public_id",      read_only=True)
    reviewer_mobile = serializers.CharField(source="reviewed_by.mobile",     read_only=True, allow_null=True)

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "public_id",
            "invoice",
            "student",
            "student_name",
            "student_pub_id",
            "mode",
            "amount",
            "paid_at",
            "reference_no",
            "proof_image",
            "status",
            "review_note",
            "reviewer_mobile",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id", "public_id", "status", "reviewed_at", "review_note",
            "student_name", "student_pub_id", "reviewer_mobile",
            "created_at", "updated_at",
        ]


class GenerateInvoicesSerializer(serializers.Serializer):
    """
    Bulk-generate invoices for all active students in a batch for a given month.
    Idempotent: skips students who already have an invoice for that period.
    """
    batch_id     = serializers.IntegerField()
    period_year  = serializers.IntegerField(min_value=2020, max_value=2100)
    period_month = serializers.IntegerField(min_value=1, max_value=12)
    due_date     = serializers.DateField()
    amount       = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_amount(self, v):
        if v <= 0:
            raise serializers.ValidationError("Amount must be greater than 0.")
        return v

    @transaction.atomic
    def save(self):
        request = self.context["request"]
        ctx     = get_tenant_context(request)
        vd      = self.validated_data

        batch = Batch.objects.filter(
            id=vd["batch_id"],
            organisation=ctx.organisation,
            branch=ctx.branch,
        ).first()
        if not batch:
            raise serializers.ValidationError({"batch_id": "Invalid batch for this branch."})

        enrollments = BatchEnrollment.objects.filter(
            batch=batch,
            status=EnrollmentStatus.ACTIVE,
        ).select_related("student")

        created = 0
        skipped = 0
        for enrollment in enrollments:
            _, was_created = FeeInvoice.objects.get_or_create(
                student=enrollment.student,
                batch=batch,
                period_year=vd["period_year"],
                period_month=vd["period_month"],
                defaults={
                    "organisation": ctx.organisation,
                    "branch":       ctx.branch,
                    "due_date":     vd["due_date"],
                    "amount":       vd["amount"],
                    "status":       InvoiceStatus.DUE,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        return {
            "created":       created,
            "skipped":       skipped,
            "batch_name":    batch.name,
            "period":        f"{vd['period_year']}-{vd['period_month']:02d}",
        }
