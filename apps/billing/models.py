from __future__ import annotations

from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.common.public_ids import invoice_public_id, txn_public_id


class PaymentSettings(TimeStampedModel):
    """
    Per-branch settings: bank account + UPI + QR
    """
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="payment_settings")
    branch = models.OneToOneField("orgs.Branch", on_delete=models.CASCADE, related_name="payment_settings")

    account_holder_name = models.CharField(max_length=120, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=40, blank=True)
    ifsc_code = models.CharField(max_length=20, blank=True)

    upi_id = models.CharField(max_length=80, blank=True)
    upi_qr_image = models.ImageField(upload_to="payments/qr/", null=True, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "bill_payment_settings"
        indexes = [
            models.Index(fields=["organisation", "is_active"]),
        ]


class FeeFrequency(models.TextChoices):
    MONTHLY = "MONTHLY", "Monthly"
    ONE_TIME = "ONE_TIME", "One Time"


class FeePlan(TimeStampedModel):
    """
    Fee structure (per batch or branch)
    """
    id = models.BigAutoField(primary_key=True)
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="fee_plans")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="fee_plans")
    batch = models.ForeignKey("academics.Batch", on_delete=models.SET_NULL, null=True, blank=True, related_name="fee_plans")

    name = models.CharField(max_length=120)
    frequency = models.CharField(max_length=10, choices=FeeFrequency.choices, default=FeeFrequency.MONTHLY)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "bill_fee_plan"
        indexes = [
            models.Index(fields=["branch", "batch"]),
            models.Index(fields=["organisation", "branch"]),
        ]


class InvoiceStatus(models.TextChoices):
    DUE = "DUE", "Due"
    PAID = "PAID", "Paid"
    PARTIAL = "PARTIAL", "Partial"
    CANCELLED = "CANCELLED", "Cancelled"


class FeeInvoice(TimeStampedModel):
    """
    Dues per student per period.
    """
    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=24, unique=True, db_index=True, editable=False)

    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="invoices")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="invoices")
    student = models.ForeignKey("academics.StudentProfile", on_delete=models.CASCADE, related_name="invoices")
    batch = models.ForeignKey("academics.Batch", on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")

    period_year = models.PositiveSmallIntegerField(db_index=True)
    period_month = models.PositiveSmallIntegerField(db_index=True)  # 1..12
    due_date = models.DateField(db_index=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=InvoiceStatus.choices, default=InvoiceStatus.DUE, db_index=True)

    class Meta:
        db_table = "bill_fee_invoice"
        constraints = [
            models.UniqueConstraint(fields=["student", "period_year", "period_month"], name="uq_student_invoice_period"),
        ]
        indexes = [
            models.Index(fields=["branch", "status", "due_date"]),
            models.Index(fields=["organisation", "status"]),
            models.Index(fields=["student", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = invoice_public_id()
        super().save(*args, **kwargs)


class PaymentMode(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank Transfer"
    UPI = "UPI", "UPI"


class TxnStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class PaymentTransaction(TimeStampedModel):
    """
    Student/Parent uploads proof; admin approves/rejects.
    """
    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=26, unique=True, db_index=True, editable=False)

    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="transactions")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="transactions")

    invoice = models.ForeignKey(FeeInvoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    student = models.ForeignKey("academics.StudentProfile", on_delete=models.CASCADE, related_name="transactions")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments_created")

    mode = models.CharField(max_length=10, choices=PaymentMode.choices, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField(default=timezone.now, db_index=True)

    reference_no = models.CharField(max_length=80, blank=True, db_index=True)
    proof_image = models.ImageField(upload_to="payments/proof/", null=True, blank=True)

    status = models.CharField(max_length=10, choices=TxnStatus.choices, default=TxnStatus.PENDING, db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments_reviewed")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "bill_payment_transaction"
        indexes = [
            models.Index(fields=["branch", "status", "paid_at"]),
            models.Index(fields=["organisation", "status", "paid_at"]),
            models.Index(fields=["student", "paid_at"]),
            models.Index(fields=["mode", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = txn_public_id()
        super().save(*args, **kwargs)


# ---------------- SaaS Subscription ----------------
class PlanCode(models.TextChoices):
    FREE = "FREE", "Free"
    STARTER = "STARTER", "Starter"
    GROWTH = "GROWTH", "Growth"
    PRO = "PRO", "Pro"
    ENTERPRISE = "ENTERPRISE", "Enterprise"


class SubscriptionPlan(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=16, choices=PlanCode.choices, unique=True)
    name = models.CharField(max_length=60)
    price_monthly_inr = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # limits (null=unlimited)
    student_limit = models.PositiveIntegerField(null=True, blank=True)
    branch_limit = models.PositiveIntegerField(null=True, blank=True)
    teacher_limit = models.PositiveIntegerField(null=True, blank=True)

    # feature flags
    feature_whatsapp_marketing = models.BooleanField(default=False)
    feature_id_cards = models.BooleanField(default=True)
    feature_reviews = models.BooleanField(default=True)
    feature_tests = models.BooleanField(default=True)
    feature_geo_attendance = models.BooleanField(default=True)

    is_public = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "bill_subscription_plan"


class SubscriptionStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PAST_DUE = "PAST_DUE", "Past Due"
    CANCELLED = "CANCELLED", "Cancelled"
    TRIAL = "TRIAL", "Trial"


class OrganisationSubscription(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    organisation = models.OneToOneField("orgs.Organisation", on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="org_subscriptions")

    status = models.CharField(max_length=12, choices=SubscriptionStatus.choices, default=SubscriptionStatus.TRIAL, db_index=True)
    started_on = models.DateField(default=timezone.localdate, db_index=True)
    expires_on = models.DateField(null=True, blank=True, db_index=True)
    trial_ends_on = models.DateField(null=True, blank=True, db_index=True)

    class Meta:
        db_table = "bill_org_subscription"
        indexes = [models.Index(fields=["status", "expires_on"])]