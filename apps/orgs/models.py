
# Create your models here.
from __future__ import annotations

import random
import string

from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.common.public_ids import org_public_id, branch_public_id

try:
    from django.contrib.gis.db.models import PointField
except Exception:
    PointField = None


def generate_join_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choice(chars) for _ in range(length))


class OrganisationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"


class Organisation(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=20, unique=True, db_index=True, editable=False)

    name = models.CharField(max_length=180, db_index=True)
    slug = models.SlugField(max_length=180, unique=True)

    owner_name = models.CharField(max_length=120, blank=True)
    owner_mobile = models.CharField(max_length=15, blank=True, db_index=True)

    status = models.CharField(max_length=12, choices=OrganisationStatus.choices, default=OrganisationStatus.PENDING, db_index=True)

    class Meta:
        db_table = "org_organisation"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["name"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = org_public_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.public_id} {self.name}"


class BranchStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"


class Branch(TimeStampedModel):
    id = models.BigAutoField(primary_key=True)
    public_id = models.CharField(max_length=20, unique=True, db_index=True, editable=False)

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="branches")

    name = models.CharField(max_length=140, db_index=True)

    # Students/Parents will type this to join
    public_code = models.CharField(max_length=12, unique=True, db_index=True)

    address_line1 = models.CharField(max_length=200)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=64, db_index=True)
    state = models.CharField(max_length=64, blank=True)
    pincode = models.CharField(max_length=12, blank=True)

    status = models.CharField(max_length=10, choices=BranchStatus.choices, default=BranchStatus.ACTIVE, db_index=True)

    # Geo fence for student attendance
    if PointField:
        geo_center = PointField(geography=True, null=True, blank=True)
    else:
        geo_center_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
        geo_center_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    geo_radius_m = models.PositiveIntegerField(default=50)

    class Meta:
        db_table = "org_branch"
        constraints = [
            models.UniqueConstraint(fields=["organisation", "name"], name="uq_branch_org_name"),
        ]
        indexes = [
            models.Index(fields=["organisation", "status"]),
            models.Index(fields=["organisation", "city"]),
            models.Index(fields=["public_code"]),
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = branch_public_id()
        if not self.public_code:
            # generate unique join code
            code = generate_join_code()
            while Branch.objects.filter(public_code=code).exists():
                code = generate_join_code()
            self.public_code = code
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.public_id} {self.name}"