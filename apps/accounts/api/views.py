from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.auth_utils import normalize_mobile
from apps.accounts.services import request_password_reset_otp, verify_otp
from apps.accounts.api.serializers import (
    OrgSignupSerializer,
    LoginSerializer,
    BranchJoinRequestSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)


class OrgSignupView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "org_signup"

    def post(self, request):
        s = OrgSignupSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.save()
        org = data["org"]
        return Response(
            {
                "organisation": {"public_id": org.public_id, "name": org.name},
                "access": data["access"],
                "refresh": data["refresh"],
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return Response(s.validated_data, status=status.HTTP_200_OK)


class BranchJoinRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "branch_join"

    def post(self, request):
        s = BranchJoinRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        req = s.save()
        return Response(
            {"status": req.status, "message": "Request submitted. Wait for admin approval."},
            status=status.HTTP_201_CREATED,
        )


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        s = ForgotPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        mobile = s.validated_data["mobile"]

        # Always return success (no user enumeration)
        request_password_reset_otp(mobile)
        return Response({"message": "If this number is registered, OTP has been sent."}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        s = ResetPasswordSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        mobile = s.validated_data["mobile"]
        otp = s.validated_data["otp"]
        new_password = s.validated_data["new_password"]

        if not verify_otp(mobile, otp):
            return Response({"detail": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(mobile=normalize_mobile(mobile)).first()
        # still do not reveal if user doesn't exist
        if not user:
            return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)

        validate_password(new_password, user=user)
        user.set_password(new_password)
        user.save(update_fields=["password", "updated_at"])
        return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)