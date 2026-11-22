"""Permission-gated, read-only staff audit log API."""
from datetime import datetime, time, timedelta

from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AdminAuditEvent


def _allowed(user):
    return bool(user.is_authenticated and user.is_active and user.is_staff and user.has_perm("accounts.view_adminauditevent"))


@method_decorator(never_cache, name="dispatch")
class AdminAuditEventListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _allowed(request.user):
            return Response(status=403)
        queryset = AdminAuditEvent.objects.all()
        actor, action, entity = (request.query_params.get(k) for k in ("actor", "action", "entity"))
        start, end = request.query_params.get("start"), request.query_params.get("end")
        if actor:
            if not actor.isdigit():
                return Response({"error": {"code": "invalid_actor"}}, status=400)
            queryset = queryset.filter(actor_id=int(actor))
        if action:
            if action not in dict(AdminAuditEvent.ACTION_CHOICES):
                return Response({"error": {"code": "invalid_action"}}, status=400)
            queryset = queryset.filter(action=action)
        if entity:
            queryset = queryset.filter(entity_type=entity[:80])
        try:
            if start:
                d = datetime.strptime(start, "%Y-%m-%d").date()
                queryset = queryset.filter(created_at__gte=timezone.make_aware(datetime.combine(d, time.min)))
            if end:
                d = datetime.strptime(end, "%Y-%m-%d").date()
                queryset = queryset.filter(created_at__lt=timezone.make_aware(datetime.combine(d + timedelta(days=1), time.min)))
        except ValueError:
            return Response({"error": {"code": "invalid_date"}}, status=400)
        try:
            page = max(1, int(request.query_params.get("page", "1")))
        except ValueError:
            return Response({"error": {"code": "invalid_page"}}, status=400)
        size, total = 50, queryset.count()
        rows = queryset[(page - 1) * size : page * size]
        return Response({
            "count": total, "page": page, "page_size": size,
            "results": [{
                "id": e.pk, "actor_id": e.actor_id,
                "actor_label": f"مدیر #{e.actor_id}" if e.actor_id else "کاربر حذف‌شده",
                "action": e.action, "method": e.method, "path": e.path,
                "entity_type": e.entity_type, "entity_id": e.entity_id,
                "response_status": e.response_status, "created_at": e.created_at, "details": e.details,
            } for e in rows],
        })
