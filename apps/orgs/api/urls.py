from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.orgs.api.views import OrganisationMeView, BranchViewSet

router = DefaultRouter()
router.register(r"branches", BranchViewSet, basename="branches")

urlpatterns = [
    path("org/me/", OrganisationMeView.as_view()),
    path("", include(router.urls)),
]