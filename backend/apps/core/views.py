"""Operational health endpoints. No business logic lives here."""
import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
@never_cache
def health(request):
    """Liveness: process is up. No dependencies touched."""
    return JsonResponse({"status": "ok"})


@require_GET
@never_cache
def ready(request):
    """Readiness: PostgreSQL and Redis (cache) are reachable."""
    checks: dict[str, str] = {}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception:
        logger.exception("Readiness: database check failed")
        checks["database"] = "error"

    try:
        cache.set("health:ping", "1", timeout=5)
        checks["cache"] = "ok" if cache.get("health:ping") == "1" else "error"
    except Exception:
        logger.exception("Readiness: cache check failed")
        checks["cache"] = "error"

    healthy = all(value == "ok" for value in checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "unavailable", "checks": checks},
        status=200 if healthy else 503,
    )

def csrf_failure(request, reason=""):
    """JSON body for CSRF rejections (CSRF_FAILURE_VIEW). The reason is logged
    by Django; it is deliberately not echoed to the client."""
    return JsonResponse(
        {"error": {"code": "csrf_failed", "message": "CSRF verification failed."}},
        status=403,
    )
