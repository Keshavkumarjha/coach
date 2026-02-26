from __future__ import annotations

from rest_framework import serializers
from apps.orgs.models import Organisation, Branch


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = [
            "public_id",
            "name",
            "slug",
            "owner_name",
            "owner_mobile",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "created_at", "updated_at", "status"]


class BranchSerializer(serializers.ModelSerializer):
    """
    Works with:
    - PostGIS: geo_center (PointField)
    - Non-PostGIS: geo_center_lat/geo_center_lng
    """

    # Make join code visible (students/parents use this)
    public_code = serializers.CharField(read_only=True)

    # Optional lat/lng input (even when using PostGIS)
    lat = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    lng = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)

    class Meta:
        model = Branch
        fields = [
            "public_id",
            "name",
            "public_code",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "pincode",
            "status",
            "geo_radius_m",
            # input helpers:
            "lat",
            "lng",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["public_id", "public_code", "created_at", "updated_at"]

    def validate(self, attrs):
        # If user provides one of lat/lng, require both
        lat = attrs.get("lat", None)
        lng = attrs.get("lng", None)
        if (lat is None) ^ (lng is None):
            raise serializers.ValidationError({"lat": "Provide both lat and lng."})
        return attrs

    def create(self, validated_data):
        lat = validated_data.pop("lat", None)
        lng = validated_data.pop("lng", None)

        branch = super().create(validated_data)

        # Save geo center
        if lat is not None and lng is not None:
            if hasattr(branch, "geo_center") and branch.geo_center is not None:
                # PostGIS PointField present
                from django.contrib.gis.geos import Point
                branch.geo_center = Point(float(lng), float(lat))  # Point(x=lng, y=lat)
                branch.save(update_fields=["geo_center", "updated_at"])
            else:
                # fallback fields
                if hasattr(branch, "geo_center_lat"):
                    branch.geo_center_lat = lat
                    branch.geo_center_lng = lng
                    branch.save(update_fields=["geo_center_lat", "geo_center_lng", "updated_at"])
        return branch

    def update(self, instance, validated_data):
        lat = validated_data.pop("lat", None)
        lng = validated_data.pop("lng", None)

        branch = super().update(instance, validated_data)

        if lat is not None and lng is not None:
            if hasattr(branch, "geo_center"):
                from django.contrib.gis.geos import Point
                branch.geo_center = Point(float(lng), float(lat))
                branch.save(update_fields=["geo_center", "updated_at"])
            else:
                if hasattr(branch, "geo_center_lat"):
                    branch.geo_center_lat = lat
                    branch.geo_center_lng = lng
                    branch.save(update_fields=["geo_center_lat", "geo_center_lng", "updated_at"])
        return branch