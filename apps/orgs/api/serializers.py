from rest_framework import serializers
from apps.orgs.models import Branch

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = [
            "public_id", "name", "public_code",
            "address_line1", "address_line2", "city", "state", "pincode",
            "status", "geo_radius_m",
        ]
        read_only_fields = ["public_id", "public_code"]