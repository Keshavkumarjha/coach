from django.urls import path
from apps.accounts.api.views import (
    OrgSignupView, LoginView, BranchJoinRequestView, ForgotPasswordView, ResetPasswordView
)

urlpatterns = [
    path("auth/org-signup/", OrgSignupView.as_view()),
    path("auth/login/", LoginView.as_view()),
    path("auth/branch-join/", BranchJoinRequestView.as_view()),
    path("auth/forgot-password/", ForgotPasswordView.as_view()),
    path("auth/reset-password/", ResetPasswordView.as_view()),
]