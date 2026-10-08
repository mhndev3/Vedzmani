"""Consistent API error envelope: {"error": {"code", "message", "details"?}}."""

from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler


def _flatten(detail):
    if isinstance(detail, dict):
        return {k: _flatten(v) for k, v in detail.items()}
    if isinstance(detail, (list, tuple)):
        return [_flatten(v) for v in detail]
    return {"code": getattr(detail, "code", "invalid"), "message": str(detail)}


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # unexpected errors stay 500; details are never leaked

    if isinstance(exc, ValidationError):
        error = {
            "code": "validation_error",
            "message": "Invalid input.",
            "details": _flatten(exc.detail),
        }
    elif isinstance(exc, APIException):
        error = {"code": exc.detail.code, "message": str(exc.detail)}
    else:  # Http404 / PermissionDenied converted by DRF
        error = {"code": "error", "message": str(response.data.get("detail", "Error."))}
    response.data = {"error": error}
    return response
