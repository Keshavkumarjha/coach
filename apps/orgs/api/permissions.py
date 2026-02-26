from __future__ import annotations
from rest_framework.permissions import BasePermission
from apps.orgs.models import Organisation


class IsOrgOwnerByMobile(BasePermission):
    """
    Temporary: org owner = Organisation.owner_mobile == request.user.mobile
    Replace later with your OrgMembership role system.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # user field name assumed: mobile
        mobile = getattr(request.user, "mobile", None)
        if not mobile:
            return False

        org = Organisation.objects.filter(owner_mobile=mobile).first()
        return org is not None