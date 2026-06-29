"""
Call lifecycle + signaling service.

The server tracks state and relays WebRTC signaling; it never carries media.
Lifecycle: initiate -> (others) join/reject -> leave/end. A call auto-ends when
the last participant leaves (ENDED if it ever connected, else MISSED).
"""

from __future__ import annotations

import json

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.utils.encoders import JSONEncoder as DRFJSONEncoder

from .broadcast import send_to_room, send_to_users
from .models import Call, CallParticipant, CallStatus, CallType, ParticipantState


def serialize_call(call: Call) -> dict:
    from .serializers import CallSerializer

    return json.loads(json.dumps(CallSerializer(call).data, cls=DRFJSONEncoder))


class CallService:
    @staticmethod
    def _ensure_conversation_member(conversation, user) -> None:
        if not conversation.participants.filter(user=user, left_at__isnull=True).exists():
            raise PermissionDenied("You are not a participant in this conversation.")

    @staticmethod
    def _conversation_user_ids(conversation) -> list:
        return list(conversation.participant_user_ids())

    # --------------------------------------------------------------- lifecycle
    @classmethod
    @transaction.atomic
    def initiate(cls, *, initiator, conversation, call_type=CallType.AUDIO) -> Call:
        cls._ensure_conversation_member(conversation, initiator)
        # Reuse an already-active call in the same conversation.
        active = Call.objects.filter(
            conversation=conversation, status__in=[CallStatus.RINGING, CallStatus.ONGOING]
        ).first()
        if active is not None:
            cls.join(user=initiator, call=active)
            return active

        call = Call.objects.create(
            conversation=conversation,
            initiator=initiator,
            type=call_type,
            status=CallStatus.RINGING,
        )
        CallParticipant.objects.create(
            call=call,
            user=initiator,
            state=ParticipantState.JOINED,
            joined_at=timezone.now(),
            is_video_on=(call_type == CallType.VIDEO),
        )
        others = [uid for uid in cls._conversation_user_ids(conversation) if uid != initiator.id]
        send_to_users(
            others,
            {
                "event": "call.incoming",
                "call": serialize_call(call),
                "from_user_id": str(initiator.id),
            },
        )
        return call

    @classmethod
    @transaction.atomic
    def join(cls, *, user, call) -> CallParticipant:
        if call.is_terminal:
            raise ValidationError("This call has already ended.")
        cls._ensure_conversation_member(call.conversation, user)
        participant, _ = CallParticipant.objects.get_or_create(
            call=call, user=user, defaults={"state": ParticipantState.INVITED}
        )
        participant.mark_joined()
        if call.status == CallStatus.RINGING:
            call.status = CallStatus.ONGOING
            call.started_at = timezone.now()
            call.save(update_fields=["status", "started_at", "updated_at"])
        send_to_room(
            call.id, {"event": "peer.joined", "call_id": str(call.id), "user_id": str(user.id)}
        )
        send_to_users(
            [call.initiator_id],
            {"event": "call.accepted", "call_id": str(call.id), "user_id": str(user.id)},
        )
        return participant

    @classmethod
    @transaction.atomic
    def reject(cls, *, user, call) -> None:
        cls._ensure_conversation_member(call.conversation, user)
        participant, _ = CallParticipant.objects.get_or_create(
            call=call, user=user, defaults={"state": ParticipantState.INVITED}
        )
        participant.state = ParticipantState.DECLINED
        participant.save(update_fields=["state", "updated_at"])
        send_to_users(
            [call.initiator_id],
            {"event": "call.rejected", "call_id": str(call.id), "user_id": str(user.id)},
        )
        # In a 1:1 call, a rejection ends it.
        if len(cls._conversation_user_ids(call.conversation)) <= 2:
            cls._terminate(call, CallStatus.REJECTED)

    @classmethod
    @transaction.atomic
    def leave(cls, *, user, call) -> None:
        participant = CallParticipant.objects.filter(call=call, user=user).first()
        if participant is not None and participant.state == ParticipantState.JOINED:
            participant.mark_left()
        send_to_room(
            call.id, {"event": "peer.left", "call_id": str(call.id), "user_id": str(user.id)}
        )
        if not call.is_terminal and call.active_participant_count() == 0:
            cls._terminate(call, CallStatus.ENDED if call.started_at else CallStatus.MISSED)

    @classmethod
    @transaction.atomic
    def end(cls, *, user, call) -> None:
        """End the whole call (initiator or any current participant)."""
        cls._ensure_conversation_member(call.conversation, user)
        cls._terminate(call, CallStatus.ENDED if call.started_at else CallStatus.CANCELLED)

    @classmethod
    def _terminate(cls, call: Call, status: str) -> None:
        if call.is_terminal:
            return
        now = timezone.now()
        call.status = status
        call.ended_at = now
        call.save(update_fields=["status", "ended_at", "updated_at"])
        CallParticipant.objects.filter(call=call, state=ParticipantState.JOINED).update(
            state=ParticipantState.LEFT, left_at=now
        )
        payload = {"event": "call.ended", "call_id": str(call.id), "status": status}
        send_to_room(call.id, payload)
        send_to_users(cls._conversation_user_ids(call.conversation), payload)

    # --------------------------------------------------------------- signaling
    @staticmethod
    def relay_signal(*, from_user, call, to_user_id, data) -> None:
        send_to_users(
            [to_user_id],
            {
                "event": "call.signal",
                "call_id": str(call.id),
                "from_user_id": str(from_user.id),
                "data": data,
            },
        )

    @staticmethod
    def update_media_state(*, user, call, **state) -> CallParticipant | None:
        participant = CallParticipant.objects.filter(call=call, user=user).first()
        if participant is None:
            return None
        for field in ("is_muted", "is_video_on", "hand_raised"):
            if state.get(field) is not None:
                setattr(participant, field, bool(state[field]))
        participant.save()
        send_to_room(
            call.id,
            {
                "event": "peer.state",
                "call_id": str(call.id),
                "user_id": str(user.id),
                "is_muted": participant.is_muted,
                "is_video_on": participant.is_video_on,
                "hand_raised": participant.hand_raised,
            },
        )
        return participant
