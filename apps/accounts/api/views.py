"""
accounts/api/views.py

All authentication endpoints — public (AllowAny), no tenant context needed.
Each view is a minimal class that delegates all logic to its serializer.

Endpoints
─────────
POST /api/auth/org-signup/        Create org + owner account → JWT tokens
POST /api/auth/login/             Mobile + password → JWT tokens + memberships
POST /api/auth/branch-join/       Student/Parent registers via branch code
POST /api/auth/forgot-password/   Request OTP (always returns 200)
POST /api/auth/reset-password/    Verify OTP + set new password
POST /api/auth/token/refresh/     (handled by simplejwt, wired in urls.py)
"""
from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.auth_utils import normalize_mobile
from apps.accounts.models import User
from apps.accounts.services import request_password_reset_otp, verify_otp
from apps.accounts.api.serializers import (
    OrgSignupSerializer,
    LoginSerializer,
    BranchJoinRequestSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)


class BaseAuthView(APIView):
    """
    Base class for all public auth endpoints.
    Sets permission to AllowAny so no authentication headers are required.
    """
    permission_classes = [AllowAny]


class OrgSignupView(BaseAuthView):
    """
    POST /api/auth/org-signup/

    Create a new Organisation + owner User in one call.
    Returns JWT access + refresh tokens.

    Body:
        org_name    string  required
        owner_name  string  required
        mobile      string  required  (10-15 digits)
        password    string  required  (min 8 chars)
    """
    throttle_scope = "org_signup"

    def post(self, request):
        serializer = OrgSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        org = data["org"]
        return Response(
            {
                "organisation": {
                    "public_id": org.public_id,
                    "name": org.name,
                },
                "access": data["access"],
                "refresh": data["refresh"],
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(BaseAuthView):
    """
    POST /api/auth/login/

    Authenticate with mobile + password.
    Returns JWT tokens + list of active memberships (org, branch, role).

    Body:
        mobile    string  required
        password  string  required
    """
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class BranchJoinRequestView(BaseAuthView):
    """
    POST /api/auth/branch-join/

    Student or Parent self-registers via Branch join code.
    Creates a PENDING join request that an admin must approve.

    Body:
        branch_code   string  required
        role          string  required  (STUDENT | PARENT)
        mobile        string  required
        password      string  required
        full_name     string  required
        admission_no  string  optional  (students)
        roll_no       string  optional
    """
    throttle_scope = "branch_join"

    def post(self, request):
        serializer = BranchJoinRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        join_request = serializer.save()
        return Response(
            {
                "status": join_request.status,
                "message": "Request submitted. Await admin approval.",
            },
            status=status.HTTP_201_CREATED,
        )


class ForgotPasswordView(BaseAuthView):
    """
    POST /api/auth/forgot-password/

    Triggers an OTP to be sent to the mobile number.
    Always returns 200 to avoid user enumeration.

    Body:
        mobile  string  required
    """
    throttle_scope = "login"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data["mobile"]
        request_password_reset_otp(mobile)
        return Response(
            {"message": "If this number is registered, an OTP has been sent."},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(BaseAuthView):
    """
    POST /api/auth/reset-password/

    Verify OTP and set new password.
    Always returns 200 to avoid user enumeration.

    Body:
        mobile        string  required
        otp           string  required  (6 digits)
        new_password  string  required  (min 8 chars)
    """
    throttle_scope = "login"

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        mobile = serializer.validated_data["mobile"]
        otp = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        if not verify_otp(mobile, otp):
            return Response(
                {"detail": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(mobile=normalize_mobile(mobile)).first()
        if user:
            validate_password(new_password, user=user)
            user.set_password(new_password)
            user.save(update_fields=["password", "updated_at"])

        # Return success even if user not found (no enumeration)
        return Response(
            {"message": "Password reset successful."},
            status=status.HTTP_200_OK,
        )
