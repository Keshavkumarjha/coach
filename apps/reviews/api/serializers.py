from __future__ import annotations

from rest_framework import serializers
from apps.reviews.models import Review, ReviewStatus


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = [
            "id",
            "author_name",
            "author_mobile",
            "rating",
            "title",
            "comment",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class ReviewModerateSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=200)