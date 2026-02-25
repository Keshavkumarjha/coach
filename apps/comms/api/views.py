from __future__ import annotations

from django.db import transaction
from rest_framework import serializers

from apps.common.tenant import get_tenant_context
from apps.comms.models import Announcement, AnnouncementBatchTarget, AudienceType
from apps.academics.models import Batch


class AnnouncementSerializer(serializers.ModelSerializer):
    batch_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)

    class Meta:
        model = Announcement
        fields = [
            "public_id",
            "title",
            "message",
            "audience_type",
            "is_pinned",
            "published_at",
            "batch_ids",
            "created_at",
        ]
        read_only_fields = ["public_id", "created_at"]

    def validate(self, attrs):
        aud = attrs.get("audience_type")
        if aud == AudienceType.BATCHES and not attrs.get("batch_ids"):
            raise serializers.ValidationError({"batch_ids": "Required when audience_type=BATCHES."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        request = self.context["request"]
        ctx = get_tenant_context(request)

        batch_ids = validated_data.pop("batch_ids", [])

        ann = Announcement.objects.create(
            organisation=ctx.organisation,
            branch=ctx.branch,
            created_by=request.user,
            **validated_data,
        )

        if ann.audience_type == AudienceType.BATCHES:
            batches = Batch.objects.filter(
                id__in=batch_ids,
                organisation=ctx.organisation,
                branch=ctx.branch,
            )
            AnnouncementBatchTarget.objects.bulk_create(
                [AnnouncementBatchTarget(announcement=ann, batch=b) for b in batches],
                ignore_conflicts=True,
            )

        return ann