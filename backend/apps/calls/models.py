"""
Calls: voice/video sessions within a conversation.

The backend is the **signaling + state** plane: it tracks who is in a call and
relays WebRTC SDP/ICE between peers (see apps.calls.consumers). Media flows
peer-to-peer (mesh) and never touches the server. Large group calls would add an
SFU; that's out of scope here and noted in the docs.

Lifecycle: RINGING -> ONGOING -> ENDED, with MISSED/REJECTED/CANCELLED terminals.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel, TimeStampedModel, UUIDModel

USER = settings.AUTH_USER_MODEL


class CallType(models.TextChoices):
    AUDIO = "audio", _("Audio")
    VIDEO = "video", _("Video")


class CallStatus(models.TextChoices):
    RINGING = "ringing", _("Ringing")
    ONGOING = "ongoing", _("Ongoing")
    ENDED = "ended", _("Ended")
    MISSED = "missed", _("Missed")
    REJECTED = "rejected", _("Rejected")
    CANCELLED = "cancelled", _("Cancelled")


class Call(BaseModel):
    conversation = models.ForeignKey(
        "chat.Conversation", on_delete=models.CASCADE, related_name="calls"
    )
    initiator = models.ForeignKey(
        USER, on_delete=models.SET_NULL, null=True, related_name="initiated_calls"
    )
    type = models.CharField(max_length=6, choices=CallType.choices, default=CallType.AUDIO)
    status = models.CharField(
        max_length=10, choices=CallStatus.choices, default=CallStatus.RINGING, db_index=True
    )
    started_at = models.DateTimeField(null=True, blank=True)  # when it became ONGOING
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "calls_call"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["conversation", "-created_at"])]

    def __str__(self) -> str:
        return f"Call<{self.type}:{self.status}:{self.id}>"

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return None

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            CallStatus.ENDED,
            CallStatus.MISSED,
            CallStatus.REJECTED,
            CallStatus.CANCELLED,
        }

    def active_participant_count(self) -> int:
        return self.participants.filter(state=ParticipantState.JOINED).count()


class ParticipantState(models.TextChoices):
    INVITED = "invited", _("Invited")
    JOINED = "joined", _("Joined")
    LEFT = "left", _("Left")
    DECLINED = "declined", _("Declined")


class CallParticipant(UUIDModel, TimeStampedModel):
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(USER, on_delete=models.CASCADE, related_name="call_participations")
    state = models.CharField(
        max_length=10, choices=ParticipantState.choices, default=ParticipantState.INVITED
    )
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    # Live media state (mirrored to peers for UI).
    is_muted = models.BooleanField(default=False)
    is_video_on = models.BooleanField(default=False)
    hand_raised = models.BooleanField(default=False)

    class Meta:
        db_table = "calls_participant"
        constraints = [
            models.UniqueConstraint(fields=["call", "user"], name="uniq_call_participant")
        ]
        indexes = [models.Index(fields=["call", "state"])]

    def __str__(self) -> str:
        return f"{self.user_id} in {self.call_id} ({self.state})"

    def mark_joined(self) -> None:
        self.state = ParticipantState.JOINED
        if self.joined_at is None:
            self.joined_at = timezone.now()
        self.save(update_fields=["state", "joined_at", "updated_at"])

    def mark_left(self) -> None:
        self.state = ParticipantState.LEFT
        self.left_at = timezone.now()
        self.save(update_fields=["state", "left_at", "updated_at"])
