"""Chat REST endpoints. Sending over REST broadcasts in realtime via ChatService."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.pagination import CursorMessagePagination

from .models import Conversation, ConversationParticipant, Message
from .serializers import (
    ConversationSerializer,
    ConversationStateSerializer,
    MessageCreateSerializer,
    MessageEditSerializer,
    MessageSerializer,
    ReactionSerializer,
    StartConversationSerializer,
)
from .services import ChatService

User = get_user_model()


def conversation_for(user, conversation_id) -> Conversation:
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if not conversation.participants.filter(user=user, left_at__isnull=True).exists():
        raise PermissionDenied("You are not a participant in this conversation.")
    return conversation


# ----------------------------------------------------------------- conversations
@extend_schema(tags=["chat"])
class ConversationListView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ConversationSerializer

    def get_queryset(self):
        return (
            Conversation.objects.filter(
                participants__user=self.request.user, participants__left_at__isnull=True
            )
            .prefetch_related("participants__user__profile", "participants__user__privacy")
            .order_by("-last_message_at", "-created_at")
            .distinct()
        )


@extend_schema(tags=["chat"])
class StartConversationView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=StartConversationSerializer, responses=ConversationSerializer)
    def post(self, request):
        serializer = StartConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        other = get_object_or_404(
            User, username=serializer.validated_data["username"], is_active=True
        )
        conversation = ChatService.get_or_create_direct(user_a=request.user, user_b=other)
        return Response(
            ConversationSerializer(conversation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["chat"])
class ConversationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=ConversationSerializer)
    def get(self, request, conversation_id):
        conversation = conversation_for(request.user, conversation_id)
        return Response(ConversationSerializer(conversation, context={"request": request}).data)


@extend_schema(tags=["chat"])
class ConversationStateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ConversationStateSerializer, summary="Pin/archive/mute a conversation")
    def patch(self, request, conversation_id):
        conversation = conversation_for(request.user, conversation_id)
        serializer = ConversationStateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ConversationParticipant.objects.filter(conversation=conversation, user=request.user).update(
            **serializer.validated_data
        )
        return Response(ConversationSerializer(conversation, context={"request": request}).data)


@extend_schema(tags=["chat"])
class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None}, summary="Mark a conversation as read")
    def post(self, request, conversation_id):
        conversation = conversation_for(request.user, conversation_id)
        ChatService.mark_read(actor=request.user, conversation=conversation)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------- messages
@extend_schema(tags=["chat"])
class MessageListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=MessageSerializer(many=True), summary="Message history (cursor paginated)"
    )
    def get(self, request, conversation_id):
        conversation = conversation_for(request.user, conversation_id)
        participant = conversation.participants.get(user=request.user)
        qs = (
            conversation.messages.select_related("sender__profile", "reply_to__sender__profile")
            .prefetch_related("reactions", "attachments__media")
            .exclude(hidden_for=request.user)
        )
        if participant.cleared_at:
            qs = qs.filter(created_at__gt=participant.cleared_at)
        paginator = CursorMessagePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(MessageSerializer(page, many=True).data)

    @extend_schema(request=MessageCreateSerializer, responses=MessageSerializer)
    def post(self, request, conversation_id):
        conversation = conversation_for(request.user, conversation_id)
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        reply_to = None
        if data.get("reply_to"):
            reply_to = get_object_or_404(Message, pk=data["reply_to"], conversation=conversation)
        metadata = {"client_id": data["client_id"]} if data.get("client_id") else {}
        message = ChatService.send_message(
            sender=request.user,
            conversation=conversation,
            text=data.get("text", ""),
            reply_to=reply_to,
            metadata=metadata,
            attachment_ids=[str(a) for a in data.get("attachment_ids", [])],
        )
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["chat"])
class MessageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_message(self, request, message_id) -> Message:
        message = get_object_or_404(Message, pk=message_id)
        conversation_for(request.user, message.conversation_id)  # membership guard
        return message

    @extend_schema(
        request=MessageEditSerializer, responses=MessageSerializer, summary="Edit a message"
    )
    def patch(self, request, message_id):
        message = self._get_message(request, message_id)
        serializer = MessageEditSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = ChatService.edit_message(
            actor=request.user, message=message, text=serializer.validated_data["text"]
        )
        return Response(MessageSerializer(message).data)

    @extend_schema(responses={204: None}, summary="Delete a message (?for_everyone=true)")
    def delete(self, request, message_id):
        message = self._get_message(request, message_id)
        for_everyone = request.query_params.get("for_everyone", "false").lower() == "true"
        ChatService.delete_message(actor=request.user, message=message, for_everyone=for_everyone)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["chat"])
class MessageReactView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ReactionSerializer, responses=MessageSerializer, summary="Toggle a reaction"
    )
    def post(self, request, message_id):
        message = get_object_or_404(Message, pk=message_id)
        conversation_for(request.user, message.conversation_id)
        serializer = ReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = ChatService.toggle_reaction(
            actor=request.user, message=message, emoji=serializer.validated_data["emoji"]
        )
        return Response(MessageSerializer(message).data)
