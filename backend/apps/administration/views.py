"""Administration, moderation, and platform endpoints."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.http import client_ip

from .models import Announcement, FeatureFlag, Report, SystemConfig
from .serializers import (
    AdminAuditLogSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
    AnnouncementSerializer,
    FeatureFlagSerializer,
    ReportCreateSerializer,
    ReportSerializer,
    ReportUpdateSerializer,
    SystemConfigSerializer,
)
from .services import AdminService

User = get_user_model()


# =============================================================== user-facing
@extend_schema(tags=["platform"])
class ReportCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ReportCreateSerializer, responses=ReportSerializer)
    def post(self, request):
        serializer = ReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = Report.objects.create(reporter=request.user, **serializer.validated_data)
        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["platform"])
class ActiveAnnouncementsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=AnnouncementSerializer(many=True))
    def get(self, request):
        now = timezone.now()
        qs = (
            Announcement.objects.filter(is_active=True)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        )
        return Response(AnnouncementSerializer(qs, many=True).data)


@extend_schema(tags=["platform"])
class EnabledFlagsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Feature flags that are enabled")
    def get(self, request):
        keys = FeatureFlag.objects.filter(is_enabled=True).values_list("key", flat=True)
        return Response({"flags": list(keys)})


@extend_schema(tags=["platform"])
class LanguagesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Supported UI languages")
    def get(self, request):
        return Response(
            {
                "default": settings.LANGUAGE_CODE,
                "languages": [
                    {"code": code, "name": str(name)} for code, name in settings.LANGUAGES
                ],
            }
        )


# =============================================================== admin-only
@extend_schema(tags=["admin"])
class DashboardView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(summary="Admin dashboard statistics")
    def get(self, request):
        return Response(AdminService.dashboard())


@extend_schema(tags=["admin"])
class ReportListView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ReportSerializer

    def get_queryset(self):
        qs = Report.objects.select_related("reporter__profile", "handled_by__profile")
        status_filter = self.request.query_params.get("status")
        return qs.filter(status=status_filter) if status_filter else qs


@extend_schema(tags=["admin"])
class ReportDetailView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(request=ReportUpdateSerializer, responses=ReportSerializer)
    def patch(self, request, report_id):
        report = get_object_or_404(Report, pk=report_id)
        serializer = ReportUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report.status = serializer.validated_data["status"]
        report.resolution_notes = serializer.validated_data.get("resolution_notes", "")
        report.handled_by = request.user
        report.save(update_fields=["status", "resolution_notes", "handled_by", "updated_at"])
        AdminService.log_action(
            actor=request.user,
            action="report.updated",
            target=str(report.id),
            metadata={"status": report.status},
            ip=client_ip(request),
        )
        return Response(ReportSerializer(report).data)


@extend_schema(tags=["admin"])
class FeatureFlagListCreateView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(responses=FeatureFlagSerializer(many=True))
    def get(self, request):
        return Response(FeatureFlagSerializer(FeatureFlag.objects.all(), many=True).data)

    @extend_schema(request=FeatureFlagSerializer, responses=FeatureFlagSerializer)
    def post(self, request):
        serializer = FeatureFlagSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flag = serializer.save()
        AdminService.log_action(
            actor=request.user, action="flag.created", target=flag.key, ip=client_ip(request)
        )
        return Response(FeatureFlagSerializer(flag).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["admin"])
class FeatureFlagDetailView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(request=FeatureFlagSerializer, responses=FeatureFlagSerializer)
    def patch(self, request, key):
        flag = get_object_or_404(FeatureFlag, key=key)
        serializer = FeatureFlagSerializer(flag, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AdminService.log_action(
            actor=request.user,
            action="flag.toggled",
            target=key,
            metadata={"is_enabled": flag.is_enabled},
            ip=client_ip(request),
        )
        return Response(FeatureFlagSerializer(flag).data)


@extend_schema(tags=["admin"])
class AnnouncementListCreateView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(responses=AnnouncementSerializer(many=True))
    def get(self, request):
        return Response(AnnouncementSerializer(Announcement.objects.all(), many=True).data)

    @extend_schema(request=AnnouncementSerializer, responses=AnnouncementSerializer)
    def post(self, request):
        serializer = AnnouncementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        announcement = serializer.save()
        AdminService.log_action(
            actor=request.user,
            action="announcement.created",
            target=str(announcement.id),
            ip=client_ip(request),
        )
        return Response(AnnouncementSerializer(announcement).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["admin"])
class AnnouncementDetailView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(request=AnnouncementSerializer, responses=AnnouncementSerializer)
    def patch(self, request, announcement_id):
        announcement = get_object_or_404(Announcement, pk=announcement_id)
        serializer = AnnouncementSerializer(announcement, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AnnouncementSerializer(announcement).data)

    @extend_schema(responses={204: None})
    def delete(self, request, announcement_id):
        get_object_or_404(Announcement, pk=announcement_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["admin"])
class SystemConfigView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(responses=SystemConfigSerializer)
    def get(self, request):
        return Response(SystemConfigSerializer(SystemConfig.get_solo()).data)

    @extend_schema(request=SystemConfigSerializer, responses=SystemConfigSerializer)
    def patch(self, request):
        config = SystemConfig.get_solo()
        serializer = SystemConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        AdminService.log_action(
            actor=request.user,
            action="system.updated",
            metadata=serializer.validated_data,
            ip=client_ip(request),
        )
        return Response(SystemConfigSerializer(config).data)


@extend_schema(tags=["admin"])
class AdminUserListView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        qs = User.objects.all().order_by("-created_at")
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))
        return qs


@extend_schema(tags=["admin"])
class AdminUserDetailView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(request=AdminUserUpdateSerializer, responses=AdminUserSerializer)
    def patch(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        serializer = AdminUserUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(target, field, value)
        target.save()
        AdminService.log_action(
            actor=request.user,
            action="user.updated",
            target=str(target.id),
            metadata=serializer.validated_data,
            ip=client_ip(request),
        )
        return Response(AdminUserSerializer(target).data)


@extend_schema(tags=["admin"])
class AuditLogListView(ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AdminAuditLogSerializer

    def get_queryset(self):
        from .models import AdminAuditLog

        return AdminAuditLog.objects.select_related("actor__profile").all()
