from rest_framework.permissions import BasePermission
from apps.accounts.models import Role
from apps.common.tenant import get_tenant_context


class IsOrgAdmin(BasePermission):
    def has_permission(self, request, view):
        ctx = get_tenant_context(request)
        return ctx.membership.role in {Role.ORG_OWNER, Role.ORG_ADMIN}


class IsBranchAdmin(BasePermission):
    def has_permission(self, request, view):
        ctx = get_tenant_context(request)
        return ctx.membership.role in {Role.ORG_OWNER, Role.ORG_ADMIN, Role.BRANCH_ADMIN}


class IsTeacher(BasePermission):
    def has_permission(self, request, view):
        ctx = get_tenant_context(request)
        return ctx.membership.role == Role.TEACHER


class IsStudentOrParent(BasePermission):
    def has_permission(self, request, view):
        ctx = get_tenant_context(request)
        return ctx.membership.role in {Role.STUDENT, Role.PARENT}