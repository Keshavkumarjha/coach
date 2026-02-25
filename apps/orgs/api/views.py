from rest_framework.viewsets import ModelViewSet
from apps.common.permissions import IsBranchAdmin
from apps.common.tenant import get_tenant_context
from apps.orgs.models import Branch
from apps.orgs.api.serializers import BranchSerializer

class BranchViewSet(ModelViewSet):
    serializer_class = BranchSerializer
    permission_classes = [IsBranchAdmin]

    def get_queryset(self):
        ctx = get_tenant_context(self.request)
        return Branch.objects.filter(organisation=ctx.organisation).order_by("-created_at")

    def perform_create(self, serializer):
        ctx = get_tenant_context(self.request)
        serializer.save(organisation=ctx.organisation)