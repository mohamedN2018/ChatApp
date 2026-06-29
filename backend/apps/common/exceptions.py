"""
Unified API error envelope.

Every error response — DRF validation errors, auth failures, 404s, and
unexpected 500s — is normalised to a single shape so the frontend has exactly
one error contract to handle:

    {
      "error": {
        "type": "validation_error",
        "message": "Invalid input.",
        "detail": {...},          # field errors or extra context
        "status_code": 400
      }
    }
"""

from __future__ import annotations

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """DRF EXCEPTION_HANDLER that wraps responses in the standard envelope."""
    # Translate native Django exceptions DRF doesn't handle by default.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = drf_exception_handler(exc, context)

    if response is None:
        # Unhandled exception -> log with traceback and return an opaque 500.
        logger.exception("Unhandled API exception", exc_info=exc)
        return Response(
            {
                "error": {
                    "type": "server_error",
                    "message": "An unexpected error occurred.",
                    "detail": None,
                    "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    error_type = exc.__class__.__name__
    if isinstance(exc, exceptions.APIException) and getattr(exc, "default_code", None):
        error_type = exc.default_code

    detail = response.data
    message = "Request failed."
    if isinstance(detail, dict) and "detail" in detail and len(detail) == 1:
        message = str(detail["detail"])
        detail = None

    response.data = {
        "error": {
            "type": error_type,
            "message": message,
            "detail": detail,
            "status_code": response.status_code,
        }
    }
    return response
