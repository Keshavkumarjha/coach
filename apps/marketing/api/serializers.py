from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from apps.common.tenant import get_tenant_context
from apps.marketing.models import (
    WhatsAppCampaign,
    WhatsAppCampaignBatchTarget,
    WhatsAppMessageLog,
    CampaignStatus,
    TargetGroup,
)
from apps.academics.models import Batch


class WhatsAppCampaignSerializer(serializers.ModelSerializer):
    batch_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)

    class Meta:
        model = WhatsAppCampaign
        fields = [
            "public_id",
            "name",
            "message",
            "target_group",
            "scheduled_at",
            "status",
            "batch_ids",
            "created_at",
        ]
        read_only_fields = ["public_id", "created_at"]

    def validate(self, attrs):
        if attrs.get("target_group") == TargetGroup.BATCHES and not attrs.get("batch_ids"):
            raise serializers.ValidationError({"batch_ids": "Required when target_group=BATCHES."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        ctx = get_tenant_context(request)
        batch_ids = validated_data.pop("batch_ids", [])

        camp = WhatsAppCampaign.objects.create(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=request.user,
            **validated_data,
        )

        if camp.target_group == TargetGroup.BATCHES:
            batches = Batch.objects.filter(id__in=batch_ids, organisation=ctx.organisation, branch=ctx.branch)
            WhatsAppCampaignBatchTarget.objects.bulk_create(
                [WhatsAppCampaignBatchTarget(campaign=camp, batch=b) for b in batches],
                ignore_conflicts=True,
            )

        return camp


class WhatsAppMessageLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppMessageLog
        fields = [
            "id",
            "to_mobile",
            "status",
            "provider_message_id",
            "error",
            "created_at",
        ]
        read_only_fields = fields