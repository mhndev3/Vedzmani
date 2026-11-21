"""Customer-owned support tickets and permission-gated staff inbox."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .models import SupportTicket, SupportTicketMessage


def _ticket_payload(ticket, include_internal=False):
    messages = ticket.messages.select_related("sender").all()
    if not include_internal:
        messages = messages.filter(is_internal=False)
    return {
        "id": ticket.pk,
        "subject": ticket.subject,
        "category": ticket.category,
        "status": ticket.status,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "customer_id": ticket.user_id,
        "messages": [{
            "id": item.pk,
            "body": item.body,
            "is_internal": item.is_internal if include_internal else False,
            "sender_is_staff": item.sender.is_staff,
            "created_at": item.created_at,
        } for item in messages],
    }


class CustomerSupportTicketListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_staff:
            return Response({"error": {"code": "customer_account_required"}}, status=403)
        tickets = SupportTicket.objects.filter(user=request.user)
        return Response({"results": [{
            "id": t.pk, "subject": t.subject, "category": t.category,
            "status": t.status, "created_at": t.created_at, "updated_at": t.updated_at,
        } for t in tickets]})

    def post(self, request):
        if request.user.is_staff:
            return Response({"error": {"code": "customer_account_required"}}, status=403)
        subject = str(request.data.get("subject", "")).strip()
        body = str(request.data.get("message", "")).strip()
        category = str(request.data.get("category", "other"))
        if not subject or len(subject) > 160 or not body or len(body) > 5000:
            return Response({"error": {"code": "invalid_ticket"}}, status=400)
        if category not in dict(SupportTicket.CATEGORY_CHOICES):
            return Response({"error": {"code": "invalid_category"}}, status=400)
        with transaction.atomic():
            ticket = SupportTicket.objects.create(user=request.user, subject=subject, category=category)
            SupportTicketMessage.objects.create(ticket=ticket, sender=request.user, body=body)
        return Response(_ticket_payload(ticket), status=status.HTTP_201_CREATED)


@method_decorator(never_cache, name="dispatch")
class CustomerSupportTicketDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):
        if request.user.is_staff:
            return Response(status=403)
        ticket = get_object_or_404(SupportTicket, pk=ticket_id, user=request.user)
        return Response(_ticket_payload(ticket))

    def post(self, request, ticket_id):
        if request.user.is_staff:
            return Response(status=403)
        ticket = get_object_or_404(SupportTicket, pk=ticket_id, user=request.user)
        if ticket.status in (SupportTicket.STATUS_RESOLVED, SupportTicket.STATUS_CLOSED):
            return Response({"error": {"code": "ticket_closed"}}, status=409)
        body = str(request.data.get("message", "")).strip()
        if not body or len(body) > 5000:
            return Response({"error": {"code": "invalid_message"}}, status=400)
        SupportTicketMessage.objects.create(ticket=ticket, sender=request.user, body=body)
        ticket.status = SupportTicket.STATUS_OPEN
        ticket.save(update_fields=["status", "updated_at"])
        return Response(_ticket_payload(ticket), status=201)


def _staff_permission(user, permission):
    return bool(user.is_authenticated and user.is_active and user.is_staff and user.has_perm(permission))


@method_decorator(never_cache, name="dispatch")
class AdminSupportTicketListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _staff_permission(request.user, "accounts.view_supportticket"):
            return Response(status=403)
        queryset = SupportTicket.objects.select_related("user").prefetch_related("messages")
        state = request.query_params.get("status")
        if state:
            if state not in dict(SupportTicket.STATUS_CHOICES):
                return Response({"error": {"code": "invalid_status"}}, status=400)
            queryset = queryset.filter(status=state)
        return Response({"results": [{
            "id": t.pk, "subject": t.subject, "category": t.category, "status": t.status,
            "customer_id": t.user_id, "created_at": t.created_at, "updated_at": t.updated_at,
            "message_count": t.messages.count(),
        } for t in queryset[:100]]})


@method_decorator(never_cache, name="dispatch")
class AdminSupportTicketDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_id):
        if not _staff_permission(request.user, "accounts.view_supportticket"):
            return Response(status=403)
        ticket = get_object_or_404(SupportTicket.objects.select_related("user"), pk=ticket_id)
        return Response(_ticket_payload(ticket, include_internal=True))

    def patch(self, request, ticket_id):
        if not _staff_permission(request.user, "accounts.change_supportticket"):
            return Response(status=403)
        ticket = get_object_or_404(SupportTicket, pk=ticket_id)
        state = request.data.get("status")
        if state not in dict(SupportTicket.STATUS_CHOICES):
            return Response({"error": {"code": "invalid_status"}}, status=400)
        ticket.status = state
        ticket.save(update_fields=["status", "updated_at"])
        return Response(_ticket_payload(ticket, include_internal=True))

    def post(self, request, ticket_id):
        if not _staff_permission(request.user, "accounts.add_supportticketmessage"):
            return Response(status=403)
        ticket = get_object_or_404(SupportTicket, pk=ticket_id)
        body = str(request.data.get("message", "")).strip()
        internal = request.data.get("is_internal", False)
        if not body or len(body) > 5000 or not isinstance(internal, bool):
            return Response({"error": {"code": "invalid_message"}}, status=400)
        with transaction.atomic():
            SupportTicketMessage.objects.create(ticket=ticket, sender=request.user, body=body, is_internal=internal)
            if not internal:
                ticket.status = SupportTicket.STATUS_WAITING_CUSTOMER
                ticket.save(update_fields=["status", "updated_at"])
        return Response(_ticket_payload(ticket, include_internal=True), status=201)
