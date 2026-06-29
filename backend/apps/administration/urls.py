"""Administration & platform routes (mounted under /api/v1/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "administration"

urlpatterns = [
    # --- user-facing platform endpoints ---
    path("reports/", views.ReportCreateView.as_view(), name="report-create"),
    path("announcements/", views.ActiveAnnouncementsView.as_view(), name="announcements"),
    path("feature-flags/", views.EnabledFlagsView.as_view(), name="flags"),
    path("i18n/languages/", views.LanguagesView.as_view(), name="languages"),
    # --- admin panel (IsAdminUser) ---
    path("admin/dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("admin/reports/", views.ReportListView.as_view(), name="admin-reports"),
    path("admin/reports/<uuid:report_id>/", views.ReportDetailView.as_view(), name="admin-report"),
    path("admin/feature-flags/", views.FeatureFlagListCreateView.as_view(), name="admin-flags"),
    path(
        "admin/feature-flags/<slug:key>/", views.FeatureFlagDetailView.as_view(), name="admin-flag"
    ),
    path(
        "admin/announcements/",
        views.AnnouncementListCreateView.as_view(),
        name="admin-announcements",
    ),
    path(
        "admin/announcements/<uuid:announcement_id>/",
        views.AnnouncementDetailView.as_view(),
        name="admin-announcement",
    ),
    path("admin/system/", views.SystemConfigView.as_view(), name="admin-system"),
    path("admin/users/", views.AdminUserListView.as_view(), name="admin-users"),
    path("admin/users/<uuid:user_id>/", views.AdminUserDetailView.as_view(), name="admin-user"),
    path("admin/audit-logs/", views.AuditLogListView.as_view(), name="admin-audit-logs"),
]
