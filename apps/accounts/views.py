from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OrgMembership, MembershipStatus
from .serializers import OrganisationSignupSerializer, LoginSerializer, BranchJoinRequestSerializer


class OrganisationSignupView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "org_signup"

    def post(self, request):
        ser = OrganisationSignupSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = ser.save()

        user = result["user"]
        org = result["organisation"]

        # Auto-login after signup
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "organisation": {"id": org.id, "public_id": getattr(org, "public_id", None), "name": org.name},
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user_id = ser.validated_data["user_id"]

        memberships = list(
            OrgMembership.objects.filter(user_id=user_id, status=MembershipStatus.ACTIVE)
            .select_related("organisation", "branch")
            .values(
                "organisation__public_id",
                "organisation__name",
                "branch__public_id",
                "branch__name",
                "role",
            )
        )

        return Response(
            {
                **ser.validated_data,
                "memberships": memberships,
            },
            status=status.HTTP_200_OK,
        )


class BranchJoinRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "branch_join"

    def post(self, request):
        ser = BranchJoinRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        req = ser.save()
        return Response(
            {
                "request_id": req.id,
                "status": req.status,
                "message": "Request submitted. Wait for admin approval.",
            },
            status=status.HTTP_201_CREATED,
        )