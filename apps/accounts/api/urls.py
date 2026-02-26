from django.urls import path
from apps.accounts.api.views import (
    OrgSignupView, LoginView, BranchJoinRequestView, ForgotPasswordView, ResetPasswordView
)

urlpatterns = [
    path("org-signup/", OrgSignupView.as_view()),
    path("login/", LoginView.as_view()),
    path("branch-join/", BranchJoinRequestView.as_view()),
    path("forgot-password/", ForgotPasswordView.as_view()),
    path("reset-password/", ResetPasswordView.as_view()),
]