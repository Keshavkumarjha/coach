# apps/api/dashboard/serializers.py

from rest_framework import serializers
from decimal import Decimal
from datetime import date, datetime

class StatCardSerializer(serializers.Serializer):
    """
    Reusable serializer for the 4 stat cards:
    - Total Revenue
    - Total Students
    - Active Batches
    - Pending Approvals
    """
    label = serializers.CharField()
    value = serializers.CharField()           # Formatted string (e.g., "₹4.5 L", "245")
    raw_value = serializers.FloatField()      # Numeric value for frontend graphs
    change_label = serializers.CharField()    # e.g. "+12% This Month"
    change_type = serializers.CharField()     # "up" | "down" | "neutral"
    alert = serializers.CharField()           # Optional alert text


class RevenueTrendItemSerializer(serializers.Serializer):
    """Single data point for the 30-day revenue line chart."""
    date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class RevenueByBatchItemSerializer(serializers.Serializer):
    """Single data point for the donut chart."""
    batch_name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    color = serializers.CharField()           # Hex color code


class PendingTransactionSerializer(serializers.Serializer):
    """Row data for the pending approvals table."""
    txn_public_id = serializers.CharField()
    student_name = serializers.CharField()
    student_initials = serializers.CharField()
    batch_name = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    mode = serializers.CharField()
    proof_url = serializers.URLField(allow_null=True)
    submitted_at = serializers.DateTimeField()


class RecentActivitySerializer(serializers.Serializer):
    """Row data for the activity feed."""
    type = serializers.CharField()            # "JOIN_REQUEST" | "PAYMENT"
    message = serializers.CharField()
    timestamp = serializers.DateTimeField()


class DashboardResponseSerializer(serializers.Serializer):
    """
    Top-level response for GET /api/dashboard/
    Matches the exact output of DashboardService.build()
    """
    # Stat Cards
    total_revenue = StatCardSerializer()
    total_students = StatCardSerializer()
    active_batches = StatCardSerializer()
    pending_approvals = StatCardSerializer()

    # Charts
    revenue_trend = RevenueTrendItemSerializer(many=True)
    revenue_by_batch = RevenueByBatchItemSerializer(many=True)

    # Tables & Lists
    pending_transactions = PendingTransactionSerializer(many=True)
    pending_transactions_total = serializers.IntegerField()
    recent_activity = RecentActivitySerializer(many=True)

    # Meta
    branch_name = serializers.CharField()
    generated_at = serializers.DateTimeField()