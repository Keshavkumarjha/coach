from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import OrgMembership, MembershipStatus
from apps.orgs.models import Organisation, Branch


@dataclass(frozen=True)
class TenantContext:
    organisation: Organisation
    branch: Optional[Branch]
    membership: OrgMembership


def get_tenant_context(request) -> TenantContext:
    """
    Resolve current org/branch from headers (recommended) and verify membership.

    Required headers:
      - X-Org: organisation public_id (e.g. ORG-26-000001)
    Optional:
      - X-Branch: branch public_id (e.g. BR-26-000001)

    This pattern is high-performance and avoids putting tenant in URL for every call.
    """
    if not request.user or not request.user.is_authenticated:
        raise PermissionDenied("Authentication required")

    org_pid = request.headers.get("X-Org") or request.query_params.get("org")
    if not org_pid:
        raise ValidationError({"X-Org": "Organisation header missing."})

    org = Organisation.objects.filter(public_id=org_pid).first()
    if not org:
        raise ValidationError({"X-Org": "Invalid organisation."})

    branch_pid = request.headers.get("X-Branch") or request.query_params.get("branch")
    branch = None
    if branch_pid:
        branch = Branch.objects.filter(public_id=branch_pid, organisation=org).first()
        if not branch:
            raise ValidationError({"X-Branch": "Invalid branch for organisation."})

    membership = (
        OrgMembership.objects
        .filter(user=request.user, organisation=org, status=MembershipStatus.ACTIVE)
        .select_related("organisation", "branch")
        .order_by("-created_at")
        .first()
    )
    if not membership:
        raise PermissionDenied("No active membership for this organisation.")

    return TenantContext(organisation=org, branch=branch, membership=membership)