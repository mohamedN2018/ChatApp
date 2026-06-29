"""Admin services: dashboard analytics and audit logging."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.calls.models import Call, CallStatus
from apps.chat.models import Message
from apps.groups.models import Group
from apps.media.models import MediaFile

from .models import AdminAuditLog, Report, ReportStatus

User = get_user_model()


class AdminService:
    @staticmethod
    def log_action(*, actor, action, target="", metadata=None, ip=None) -> AdminAuditLog:
        return AdminAuditLog.objects.create(
            actor=actor, action=action, target=str(target), metadata=metadata or {}, ip_address=ip
        )

    @staticmethod
    def _daily_series(queryset, days=14) -> list[dict]:
        since = timezone.now() - timedelta(days=days)
        rows = (
            queryset.filter(created_at__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        return [{"date": r["day"].isoformat(), "count": r["count"]} for r in rows]

    @classmethod
    def dashboard(cls) -> dict:
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        storage_bytes = MediaFile.objects.aggregate(total=Sum("size"))["total"] or 0
        return {
            "users": {
                "total": User.objects.count(),
                "active": User.objects.filter(is_active=True).count(),
                "verified": User.objects.filter(is_email_verified=True).count(),
                "new_7d": User.objects.filter(created_at__gte=week_ago).count(),
            },
            "messages": {
                "total": Message.objects.count(),
                "new_7d": Message.objects.filter(created_at__gte=week_ago).count(),
            },
            "calls": {
                "total": Call.objects.count(),
                "ongoing": Call.objects.filter(status=CallStatus.ONGOING).count(),
            },
            "groups": {"total": Group.objects.count()},
            "media": {"count": MediaFile.objects.count(), "storage_bytes": storage_bytes},
            "reports": {"pending": Report.objects.filter(status=ReportStatus.PENDING).count()},
            "charts": {
                "signups": cls._daily_series(User.objects),
                "messages": cls._daily_series(Message.objects),
            },
        }
