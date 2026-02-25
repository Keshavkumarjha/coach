from django.urls import path
from .views import OrganisationSignupView, LoginView, BranchJoinRequestView

urlpatterns = [
    path("auth/org-signup/", OrganisationSignupView.as_view(), name="org-signup"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/branch-join/", BranchJoinRequestView.as_view(), name="branch-join"),
]