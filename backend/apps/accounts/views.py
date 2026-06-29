"""
Authentication & account API views.

Views are deliberately thin: validate input, derive request context, delegate to
``AuthService``, and shape the response. All business rules live in the service.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.common.http import client_ip, device_label, user_agent

from .models import SecurityEvent, SecurityEventType, UserSession
from .serializers import (
    ChangePasswordSerializer,
    EmailVerificationSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    SecurityEventSerializer,
    SessionTokenRefreshSerializer,
    TokenPairSerializer,
    UserSerializer,
    UserSessionSerializer,
)
from .services import AuthService, RequestContext


def _ctx(request) -> RequestContext:
    return RequestContext(
        ip=client_ip(request),
        user_agent=user_agent(request),
        device_label=device_label(request),
    )


def _current_sid(request):
    auth = request.auth
    return auth.get("sid") if auth is not None and hasattr(auth, "get") else None


# --------------------------------------------------------------- registration
@extend_schema(tags=["auth"])
class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(
        request=RegisterSerializer,
        responses={201: OpenApiResponse(description="Account created; verification email sent.")},
        summary="Register a new account",
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = AuthService.register(
            email=data["email"],
            username=data["username"],
            password=data["password"],
            display_name=data.get("display_name", ""),
            ctx=_ctx(request),
        )
        return Response(
            {
                "detail": "Registration successful. Check your email to verify your account.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["auth"])
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "verify_email"

    @extend_schema(request=EmailVerificationSerializer, summary="Verify email address")
    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AuthService.verify_email(
            raw_token=serializer.validated_data["token"], ctx=_ctx(request)
        )
        if user is None:
            raise drf_serializers.ValidationError(
                {"token": "Invalid or expired verification token."}
            )
        return Response(
            {"detail": "Email verified successfully.", "user": UserSerializer(user).data}
        )


@extend_schema(tags=["auth"])
class ResendVerificationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "resend_verification"

    @extend_schema(request=ResendVerificationSerializer, summary="Resend verification email")
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.resend_verification(email=serializer.validated_data["email"])
        # Always identical response — never reveal whether the email is registered.
        return Response(
            {"detail": "If the account exists and is unverified, a new email has been sent."}
        )


# ----------------------------------------------------------------------- login
@extend_schema(tags=["auth"])
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        request=LoginSerializer,
        responses={200: TokenPairSerializer},
        summary="Log in (email + password)",
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except drf_serializers.ValidationError:
            email = (request.data.get("email") or "").lower().strip()
            AuthService.log_event(
                SecurityEventType.LOGIN_FAILED,
                user=None,
                ctx=_ctx(request),
                email=email,
            )
            raise
        user = serializer.validated_data["user"]
        access, refresh, _session = AuthService.login(user=user, ctx=_ctx(request))
        return Response({"access": access, "refresh": refresh, "user": UserSerializer(user).data})


@extend_schema(tags=["auth"])
class SessionTokenRefreshView(TokenRefreshView):
    """Rotate tokens, enforcing that the backing session is still active."""

    serializer_class = SessionTokenRefreshSerializer


@extend_schema(tags=["auth"])
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LogoutSerializer,
        responses={204: OpenApiResponse(description="Logged out; session revoked.")},
        summary="Log out (revoke this session)",
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.logout(
            user=request.user,
            refresh_token=serializer.validated_data["refresh"],
            ctx=_ctx(request),
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------- password recovery
@extend_schema(tags=["auth"])
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetRequestSerializer, summary="Request a password reset")
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.request_password_reset(
            email=serializer.validated_data["email"], ctx=_ctx(request)
        )
        return Response(
            {"detail": "If an account exists for this email, a reset link has been sent."}
        )


@extend_schema(tags=["auth"])
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetConfirmSerializer, summary="Confirm a password reset")
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = AuthService.reset_password(
            raw_token=serializer.validated_data["token"],
            new_password=serializer.validated_data["new_password"],
            ctx=_ctx(request),
        )
        if user is None:
            raise drf_serializers.ValidationError({"token": "Invalid or expired reset token."})
        return Response({"detail": "Password has been reset. Please sign in."})


@extend_schema(tags=["account"])
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer, summary="Change password (signs out other devices)"
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        AuthService.change_password(
            user=request.user,
            new_password=serializer.validated_data["new_password"],
            current_session_id=_current_sid(request),
            ctx=_ctx(request),
        )
        return Response({"detail": "Password changed successfully."})


# --------------------------------------------------------------------- account
@extend_schema(tags=["account"])
class MeView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    @extend_schema(summary="Get the current user")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_object(self):
        return self.request.user


@extend_schema(tags=["account"])
class SessionListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSessionSerializer

    @extend_schema(summary="List active devices / sessions")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return UserSession.objects.filter(user=self.request.user)

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["current_session_id"] = _current_sid(self.request)
        return ctx


@extend_schema(tags=["account"])
class SessionRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={204: OpenApiResponse(description="Session revoked.")},
        summary="Revoke a session (sign out a device)",
    )
    def delete(self, request, session_id):
        revoked = AuthService.revoke_session(
            user=request.user, session_id=session_id, ctx=_ctx(request)
        )
        if not revoked:
            raise NotFound("Session not found.")
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["account"])
class SecurityEventListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SecurityEventSerializer

    @extend_schema(summary="List the account's security log (login history & events)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        return SecurityEvent.objects.filter(user=self.request.user)
