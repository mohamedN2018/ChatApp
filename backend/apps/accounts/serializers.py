"""DRF serializers for the authentication & account endpoints."""

from __future__ import annotations

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import SecurityEvent, UserSession
from .tokens import is_session_revoked

User = get_user_model()


# --------------------------------------------------------------------- helpers
class _PasswordPairMixin:
    """Validates a new password against Django validators + a confirmation field."""

    password_field = "password"
    confirm_field = "password_confirm"

    def _validate_password_pair(self, attrs, *, user=None):
        password = attrs.get(self.password_field)
        confirm = attrs.get(self.confirm_field)
        if password != confirm:
            raise serializers.ValidationError({self.confirm_field: _("Passwords do not match.")})
        validate_password(password, user=user)
        return attrs


# ------------------------------------------------------------------ user output
class UserSerializer(serializers.ModelSerializer):
    """Public-facing representation of the authenticated user."""

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "display_name",
            "is_email_verified",
            "is_verified",
            "last_seen_at",
            "created_at",
        )
        read_only_fields = fields


# ----------------------------------------------------------------- registration
class RegisterSerializer(_PasswordPairMixin, serializers.Serializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=32)
    display_name = serializers.CharField(max_length=80, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_email(self, value: str) -> str:
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("An account with this email already exists."))
        return value

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(_("This username is already taken."))
        return value

    def validate(self, attrs):
        # Build an unsaved user so similarity validation can compare against
        # email/username without hitting the DB.
        probe = User(email=attrs["email"], username=attrs["username"])
        return self._validate_password_pair(attrs, user=probe)


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField()


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


# ------------------------------------------------------------------------ login
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(
            request,
            username=attrs["email"].lower().strip(),
            password=attrs["password"],
        )
        if user is None:
            # Generic message: don't reveal whether the email exists or the
            # account is inactive.
            raise serializers.ValidationError(
                _("Invalid email or password."), code="invalid_credentials"
            )
        attrs["user"] = user
        return attrs


class TokenPairSerializer(serializers.Serializer):
    """Response shape for login (documents the OpenAPI schema)."""

    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class SessionTokenRefreshSerializer(TokenRefreshSerializer):
    """Refresh that also enforces the backing session is still active."""

    def validate(self, attrs):
        incoming = RefreshToken(attrs["refresh"])  # verifies signature + blacklist
        sid = incoming.get("sid")
        session = None
        if sid:
            session = UserSession.objects.filter(pk=sid).first()
            if session is None or not session.is_active or is_session_revoked(str(sid)):
                raise InvalidToken(_("This session is no longer active."))
        data = super().validate(attrs)  # rotates + blacklists old token
        if session is not None:
            session.touch()
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


# ------------------------------------------------------------- password recovery
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(_PasswordPairMixin, serializers.Serializer):
    password_field = "new_password"
    confirm_field = "new_password_confirm"

    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        return self._validate_password_pair(attrs)


class ChangePasswordSerializer(_PasswordPairMixin, serializers.Serializer):
    password_field = "new_password"
    confirm_field = "new_password_confirm"

    current_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_current_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(_("Current password is incorrect."))
        return value

    def validate(self, attrs):
        return self._validate_password_pair(attrs, user=self.context["request"].user)


# --------------------------------------------------------------------- sessions
class UserSessionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserSession
        fields = (
            "id",
            "device_label",
            "user_agent",
            "ip_address",
            "last_used_at",
            "created_at",
            "expires_at",
            "revoked_at",
            "is_active",
            "is_current",
        )
        read_only_fields = fields

    def get_is_current(self, obj) -> bool:
        return str(obj.id) == str(self.context.get("current_session_id"))


class SecurityEventSerializer(serializers.ModelSerializer):
    event_type_display = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = SecurityEvent
        fields = (
            "id",
            "event_type",
            "event_type_display",
            "ip_address",
            "user_agent",
            "metadata",
            "created_at",
        )
        read_only_fields = fields
