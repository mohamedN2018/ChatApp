"""Call REST endpoints: initiate, history, accept/reject/end, ICE servers."""

from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.chat.models import Conversation

from .models import Call
from .serializers import CallSerializer, InitiateCallSerializer
from .services import CallService


def _call_for(user, call_id) -> Call:
    call = get_object_or_404(Call, pk=call_id)
    CallService._ensure_conversation_member(call.conversation, user)
    return call


@extend_schema(tags=["calls"])
class InitiateCallView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=InitiateCallSerializer, responses=CallSerializer)
    def post(self, request):
        serializer = InitiateCallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = get_object_or_404(
            Conversation, pk=serializer.validated_data["conversation_id"]
        )
        call = CallService.initiate(
            initiator=request.user,
            conversation=conversation,
            call_type=serializer.validated_data["type"],
        )
        return Response(CallSerializer(call).data, status=201)


@extend_schema(tags=["calls"])
class CallHistoryView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CallSerializer

    def get_queryset(self):
        return (
            Call.objects.filter(
                conversation__participants__user=self.request.user,
                conversation__participants__left_at__isnull=True,
            )
            .select_related("initiator__profile")
            .prefetch_related("participants__user__profile")
            .distinct()
        )


@extend_schema(tags=["calls"])
class CallDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CallSerializer)
    def get(self, request, call_id):
        return Response(CallSerializer(_call_for(request.user, call_id)).data)


@extend_schema(tags=["calls"])
class AcceptCallView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CallSerializer, summary="Accept (join) a call")
    def post(self, request, call_id):
        call = _call_for(request.user, call_id)
        CallService.join(user=request.user, call=call)
        call.refresh_from_db()
        return Response(CallSerializer(call).data)


@extend_schema(tags=["calls"])
class RejectCallView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None}, summary="Reject a call")
    def post(self, request, call_id):
        CallService.reject(user=request.user, call=_call_for(request.user, call_id))
        return Response(status=204)


@extend_schema(tags=["calls"])
class EndCallView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None}, summary="End / leave a call")
    def post(self, request, call_id):
        call = _call_for(request.user, call_id)
        # "end=true" terminates the whole call; otherwise just leave.
        if str(request.data.get("end", "")).lower() == "true":
            CallService.end(user=request.user, call=call)
        else:
            CallService.leave(user=request.user, call=call)
        return Response(status=204)


@extend_schema(tags=["calls"])
class IceServersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="WebRTC ICE servers (STUN/TURN) for the client")
    def get(self, request):
        return Response({"iceServers": settings.WEBRTC_ICE_SERVERS})
