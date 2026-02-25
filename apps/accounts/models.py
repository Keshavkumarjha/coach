# Create your models here. accounts/models.py
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel

MOBILE_VALIDATOR = RegexValidator(regex=r"^\d{10,15}$", message="Mobile must be 10-15 digits.")

def normalize_mobile(mobile: str) -> str:
    return "".join(ch for ch in str(mobile or "") if ch.isdigit())


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, mobile: str, password: str | None, **extra_fields):
        mobile = normalize_mobile(mobile)
        if not mobile:
            raise ValueError("Mobile is required")
        user = self.model(mobile=mobile, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, mobile: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(mobile, password, **extra_fields)

    def create_superuser(self, mobile: str, password: str, **extra_fields):
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(mobile, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    mobile = models.CharField(max_length=15, unique=True, validators=[MOBILE_VALIDATOR], db_index=True)
    full_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True, null=True)

    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False, db_index=True)

    objects = UserManager()

    USERNAME_FIELD = "mobile"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "auth_user_mobile"
        indexes = [
            models.Index(fields=["mobile"]),
            models.Index(fields=["is_active", "is_staff"]),
        ]

    def save(self, *args, **kwargs):
        if self.mobile:
            self.mobile = normalize_mobile(self.mobile)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.mobile} ({self.full_name or 'User'})"


class Role(models.TextChoices):
    ORG_OWNER = "ORG_OWNER", "Org Owner"
    ORG_ADMIN = "ORG_ADMIN", "Org Admin"
    BRANCH_ADMIN = "BRANCH_ADMIN", "Branch Admin"
    TEACHER = "TEACHER", "Teacher"
    STAFF = "STAFF", "Staff"
    STUDENT = "STUDENT", "Student"
    PARENT = "PARENT", "Parent"


class MembershipStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    PENDING = "PENDING", "Pending"
    SUSPENDED = "SUSPENDED", "Suspended"
    REJECTED = "REJECTED", "Rejected"


class OrgMembership(TimeStampedModel):
    """
    Multi-tenant: user can be in multiple orgs & branches with different roles.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="memberships")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships")

    role = models.CharField(max_length=20, choices=Role.choices, db_index=True)
    status = models.CharField(max_length=12, choices=MembershipStatus.choices, default=MembershipStatus.PENDING, db_index=True)

    class Meta:
        db_table = "org_membership"
        constraints = [
            models.UniqueConstraint(fields=["user", "organisation", "role", "branch"], name="uq_user_org_role_branch"),
        ]
        indexes = [
            models.Index(fields=["organisation", "role", "status"]),
            models.Index(fields=["branch", "role", "status"]),
            models.Index(fields=["user", "status"]),
        ]


class JoinRole(models.TextChoices):
    STUDENT = "STUDENT", "Student"
    PARENT = "PARENT", "Parent"


class JoinStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class BranchJoinRequest(TimeStampedModel):
    """
    Student/Parent registers using Branch public_code and mobile, waits approval.
    """
    organisation = models.ForeignKey("orgs.Organisation", on_delete=models.CASCADE, related_name="join_requests")
    branch = models.ForeignKey("orgs.Branch", on_delete=models.CASCADE, related_name="join_requests")

    role = models.CharField(max_length=10, choices=JoinRole.choices, db_index=True)

    mobile = models.CharField(max_length=15, db_index=True)
    full_name = models.CharField(max_length=120, blank=True)

    admission_no = models.CharField(max_length=32, blank=True, db_index=True)  # optional
    roll_no = models.CharField(max_length=20, blank=True)

    status = models.CharField(max_length=10, choices=JoinStatus.choices, default=JoinStatus.PENDING, db_index=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="join_requests_decided")
    decided_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        db_table = "acct_branch_join_request"
        indexes = [
            models.Index(fields=["branch", "role", "status", "created_at"]),
            models.Index(fields=["organisation", "status"]),
            models.Index(fields=["mobile", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "role", "mobile"],
                name="uq_branch_role_mobile_pending",
                condition=models.Q(status="PENDING"),
            )
        ]

    def save(self, *args, **kwargs):
        if self.mobile:
            self.mobile = normalize_mobile(self.mobile)
        super().save(*args, **kwargs)