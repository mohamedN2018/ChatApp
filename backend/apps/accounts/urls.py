"""Account & authentication routes (mounted under /api/v1/accounts/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # Registration & email verification
    path("register/", views.RegisterView.as_view(), name="register"),
    path("verify-email/", views.VerifyEmailView.as_view(), name="verify-email"),
    path(
        "resend-verification/", views.ResendVerificationView.as_view(), name="resend-verification"
    ),
    # Session lifecycle
    path("login/", views.LoginView.as_view(), name="login"),
    path("token/refresh/", views.SessionTokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    # Password recovery & change
    path("password/reset/", views.PasswordResetRequestView.as_view(), name="password-reset"),
    path(
        "password/reset/confirm/",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    path("password/change/", views.ChangePasswordView.as_view(), name="password-change"),
    # Account
    path("me/", views.MeView.as_view(), name="me"),
    path("sessions/", views.SessionListView.as_view(), name="session-list"),
    path("sessions/<uuid:session_id>/", views.SessionRevokeView.as_view(), name="session-revoke"),
    path("security-log/", views.SecurityEventListView.as_view(), name="security-log"),
]
