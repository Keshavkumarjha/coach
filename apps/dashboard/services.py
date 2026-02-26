"""
apps/api/dashboard/service.py

All heavy DB queries for the admin dashboard live here — keeps the view thin.

Design: DashboardService is instantiated once per request with (org, branch)
and exposes a single public method `build()` that returns the full payload dict.

Each private method computes one widget's data and returns plain Python dicts,
which the view passes into DashboardResponseSerializer for type-safe output.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.academics.models import Batch, StudentProfile, BatchStatus
from apps.accounts.models import BranchJoinRequest, JoinStatus
from apps.attendance.models import ClassSession, SessionStatus
from apps.billing.models import (
    FeeInvoice,
    InvoiceStatus,
    PaymentTransaction,
    TxnStatus,
)
from apps.orgs.models import Organisation, Branch


# Donut chart palette — assigned by batch position (consistent across requests)
_BATCH_COLORS = [
    "#6366f1",  # indigo
    "#22d3ee",  # cyan
    "#4ade80",  # green
    "#facc15",  # yellow
    "#f87171",  # red
    "#fb923c",  # orange
    "#a78bfa",  # violet
    "#34d399",  # emerald
]


class DashboardService:
    """
    Computes all dashboard widgets for a given (organisation, branch).

    Usage:
        data = DashboardService(org, branch).build()
        serializer = DashboardResponseSerializer(data)
    """

    def __init__(self, organisation: Organisation, branch: Branch) -> None:
        self.org = organisation
        self.branch = branch

    # ── Public entry point ────────────────────────────────────────────────────

    def build(self) -> dict:
        """Build and return the complete dashboard payload."""
        pending_txns, pending_txns_total = self._pending_transactions()
        return {
            # stat cards
            "total_revenue":      self._revenue_card(),
            "total_students":     self._students_card(),
            "active_batches":     self._batches_card(),
            "pending_approvals":  self._pending_approvals_card(),
            # charts
            "revenue_trend":      self._revenue_trend(),
            "revenue_by_batch":   self._revenue_by_batch(),
            # table
            "pending_transactions":       pending_txns,
            "pending_transactions_total": pending_txns_total,
            # activity feed
            "recent_activity": self._recent_activity(),
            # meta
            "branch_name":  self.branch.name,
            "generated_at": timezone.now(),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_inr(amount: Decimal) -> str:
        """Format currency: 450000 → '₹4.5 L', 1200 → '₹1,200', 50 → '₹50'"""
        if amount >= 100_000:
            return f"₹{amount / 100_000:.1f} L"
        if amount >= 1_000:
            return f"₹{amount:,.0f}"
        return f"₹{amount}"

    @staticmethod
    def _initials(name: str) -> str:
        """'Rahul Kumar' → 'RK', '' → '??'"""
        parts = name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return name[:2].upper() if name else "??"

    def _approved_txns(self):
        return PaymentTransaction.objects.filter(
            organisation=self.org,
            branch=self.branch,
            status=TxnStatus.APPROVED,
        )

    # ── Stat cards ────────────────────────────────────────────────────────────

    def _revenue_card(self) -> dict:
        """Total approved revenue (all-time headline) with month-over-month change."""
        today = timezone.localdate()
        this_month_start = today.replace(day=1)
        last_month_end = this_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        base = self._approved_txns()
        all_total: Decimal = base.aggregate(t=Sum("amount"))["t"] or Decimal("0")
        this_total: Decimal = (
            base.filter(paid_at__date__gte=this_month_start)
            .aggregate(t=Sum("amount"))["t"] or Decimal("0")
        )
        last_total: Decimal = (
            base.filter(
                paid_at__date__gte=last_month_start,
                paid_at__date__lte=last_month_end,
            )
            .aggregate(t=Sum("amount"))["t"] or Decimal("0")
        )

        if last_total > 0:
            pct = ((this_total - last_total) / last_total) * 100
            change_label = f"+{pct:.0f}% This Month" if pct >= 0 else f"{pct:.0f}% This Month"
            change_type = "up" if pct >= 0 else "down"
        else:
            change_label = "First month data"
            change_type = "neutral"

        return {
            "label": "Total Revenue",
            "value": self._fmt_inr(all_total),
            "raw_value": float(all_total),
            "change_label": change_label,
            "change_type": change_type,
            "alert": "",
        }

    def _students_card(self) -> dict:
        """Active student count with new-this-month delta."""
        month_start = timezone.localdate().replace(day=1)
        total = StudentProfile.objects.filter(
            organisation=self.org,
            branch=self.branch,
            is_active_for_login=True,
        ).count()
        new_this_month = StudentProfile.objects.filter(
            organisation=self.org,
            branch=self.branch,
            is_active_for_login=True,
            created_at__date__gte=month_start,
        ).count()
        return {
            "label": "Total Students",
            "value": f"{total:,}",
            "raw_value": float(total),
            "change_label": f"+{new_this_month} New This Month",
            "change_type": "up" if new_this_month > 0 else "neutral",
            "alert": "",
        }

    def _batches_card(self) -> dict:
        """Active batch count with open-sessions alert."""
        total = Batch.objects.filter(
            organisation=self.org,
            branch=self.branch,
            status=BatchStatus.ACTIVE,
        ).count()
        open_sessions = ClassSession.objects.filter(
            organisation=self.org,
            branch=self.branch,
            status=SessionStatus.OPEN,
        ).count()
        return {
            "label": "Active Batches",
            "value": str(total),
            "raw_value": float(total),
            "change_label": "",
            "change_type": "neutral",
            "alert": f"{open_sessions} Active Sessions" if open_sessions else "",
        }

    def _pending_approvals_card(self) -> dict:
        """Combined join requests + payment proofs pending admin action."""
        join_count = BranchJoinRequest.objects.filter(
            organisation=self.org,
            branch=self.branch,
            status=JoinStatus.PENDING,
        ).count()
        txn_count = PaymentTransaction.objects.filter(
            organisation=self.org,
            branch=self.branch,
            status=TxnStatus.PENDING,
        ).count()
        total = join_count + txn_count
        return {
            "label": "Pending Approvals",
            "value": str(total),
            "raw_value": float(total),
            "change_label": f"{join_count} Join · {txn_count} Payments",
            "change_type": "down" if total > 0 else "neutral",
            "alert": "Action Required" if total > 0 else "",
        }

    # ── Charts ────────────────────────────────────────────────────────────────

    def _revenue_trend(self, days: int = 30) -> list[dict]:
        """Daily approved revenue for the last `days` days — fills 0 for missing days."""
        today = timezone.localdate()
        start = today - timedelta(days=days - 1)

        rows = (
            self._approved_txns()
            .filter(paid_at__date__gte=start)
            .annotate(day=TruncDate("paid_at"))
            .values("day")
            .annotate(amount=Sum("amount"))
            .order_by("day")
        )

        day_map: dict[date, Decimal] = {r["day"]: r["amount"] for r in rows}
        return [
            {
                "date": start + timedelta(days=i),
                "amount": day_map.get(start + timedelta(days=i), Decimal("0")),
            }
            for i in range(days)
        ]

    def _revenue_by_batch(self) -> list[dict]:
        """Top 8 batches by approved revenue — for donut chart."""
        rows = (
            self._approved_txns()
            .values("invoice__batch__name")
            .annotate(amount=Sum("amount"))
            .order_by("-amount")[:8]
        )
        return [
            {
                "batch_name": row["invoice__batch__name"] or "Other",
                "amount": row["amount"] or Decimal("0"),
                "color": _BATCH_COLORS[i % len(_BATCH_COLORS)],
            }
            for i, row in enumerate(rows)
        ]

    # ── Pending transactions table ────────────────────────────────────────────

    def _pending_transactions(self, limit: int = 20) -> tuple[list[dict], int]:
        """Returns (rows, total_count) for the pending payment approvals table."""
        qs = (
            PaymentTransaction.objects
            .filter(
                organisation=self.org,
                branch=self.branch,
                status=TxnStatus.PENDING,
            )
            .select_related(
                "student", "student__user",
                "invoice", "invoice__batch",
            )
            .order_by("-created_at")
        )
        total = qs.count()
        rows = []
        for txn in qs[:limit]:
            student_name = txn.student.user.full_name or txn.student.user.mobile
            batch_name = (
                txn.invoice.batch.name
                if txn.invoice and txn.invoice.batch
                else "—"
            )
            rows.append({
                "txn_public_id":    txn.public_id,
                "student_name":     student_name,
                "student_initials": self._initials(student_name),
                "batch_name":       batch_name,
                "amount":           txn.amount,
                "mode":             txn.mode,
                "proof_url":        txn.proof_image.url if txn.proof_image else None,
                "submitted_at":     txn.created_at,
            })
        return rows, total

    # ── Recent activity feed ──────────────────────────────────────────────────

    def _recent_activity(self, limit: int = 10) -> list[dict]:
        """Merges join requests + payment submissions into a unified feed."""
        feed: list[dict] = []

        for jr in (
            BranchJoinRequest.objects
            .filter(organisation=self.org, branch=self.branch)
            .order_by("-created_at")[:limit]
        ):
            feed.append({
                "type": "JOIN_REQUEST",
                "message": f"{jr.full_name or jr.mobile} requested to join as {jr.role}",
                "timestamp": jr.created_at,
            })

        for txn in (
            PaymentTransaction.objects
            .filter(organisation=self.org, branch=self.branch)
            .select_related("student", "student__user")
            .order_by("-created_at")[:limit]
        ):
            name = txn.student.user.full_name or txn.student.user.mobile
            feed.append({
                "type": "PAYMENT",
                "message": f"{name} submitted ₹{txn.amount:,.0f} via {txn.mode}",
                "timestamp": txn.created_at,
            })

        feed.sort(key=lambda x: x["timestamp"], reverse=True)
        return feed[:limit]
