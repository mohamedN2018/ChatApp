"""Session-aware JWT authentication.

Extends SimpleJWT to reject access tokens whose backing session has been revoked,
enabling instant logout / "sign out this device" even though access tokens are
otherwise stateless and short-lived.
"""

from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from .tokens import SESSION_CLAIM, is_session_revoked


class SessionAwareJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        token = super().get_validated_token(raw_token)
        sid = token.get(SESSION_CLAIM)
        if sid and is_session_revoked(str(sid)):
            raise InvalidToken("This session has been revoked.")
        return token
