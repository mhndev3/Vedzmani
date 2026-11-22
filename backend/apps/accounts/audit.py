"""Privacy-safe audit capture for authenticated staff mutations."""
import logging
import re

from django.utils import timezone

logger = logging.getLogger(__name__)
_NUMERIC_ID = re.compile(r"/(\d+)/?$")


class AdminAuditMiddleware:
    """Record staff write attempts without retaining request/response bodies."""

    WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        path = request.path_info or request.path
        if (
            request.method in self.WRITE_METHODS
            and path.startswith(("/api/admin/", "/admin/"))
            and user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_active", False)
            and getattr(user, "is_staff", False)
            and not path.startswith(("/api/admin/audit-log/", "/api/admin/staff/"))
        ):
            try:
                from .models import AdminAuditEvent

                segments = [part for part in path.strip("/").split("/") if part]
                object_match = _NUMERIC_ID.search(path)
                object_id = int(object_match.group(1)) if object_match else None
                entity_type = segments[3] if len(segments) > 3 and segments[1] == "admin" else (
                    segments[1] if len(segments) > 1 else "admin"
                )
                AdminAuditEvent.objects.create(
                    actor_id=user.pk,
                    action=request.method.lower(),
                    method=request.method,
                    path=path[:255],
                    entity_type=entity_type[:80],
                    entity_id=object_id,
                    response_status=response.status_code,
                )
            except Exception:
                # Audit failure must not replace the original business response.
                logger.exception("admin_audit_event_write_failed")
        return response
