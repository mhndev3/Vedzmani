"""Read-only customer directory for the custom staff workspace.

This endpoint deliberately exposes no direct customer PII. Contact details, addresses, national
identifiers and profile fields remain outside this workspace; the existing order PII permission
continues to govern delivery snapshots in the order workspace.
"""
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from apps.orders.models import Order


class StaffCustomerViewPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active and user.is_staff
            and user.has_perm("accounts.view_user")
        )


def customer_queryset():
    return (
        User.objects.filter(is_staff=False, is_superuser=False)
        .annotate(
            order_count=Count("orders", distinct=True),
            # "Total spent" must include only successfully paid orders. Pending and failed
            # orders remain part of the order count, but are not completed customer spend.
            total_spent=Sum(
                "orders__total",
                filter=Q(orders__payment_status=Order.PAID),
            ),
        )
        .order_by("-date_joined", "-id")
    )


def serialize_customer(customer):
    phone = customer.phone or ""
    masked = f"{phone[:5]}****{phone[-3:]}" if len(phone) > 8 else "****"
    return {
        "id": customer.id,
        "phone_masked": masked,
        "is_active": customer.is_active,
        "date_joined": customer.date_joined,
        "order_count": customer.order_count,
        "total_spent": str(customer.total_spent or 0),
        "pii_hidden": True,
    }


class AdminCustomerPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


@method_decorator(never_cache, name="dispatch")
class AdminCustomerListView(APIView):
    permission_classes = [StaffCustomerViewPermission]
    pagination_class = AdminCustomerPagination

    def get(self, request):
        queryset = customer_queryset()
        active_filter = request.query_params.get("active")
        if active_filter not in (None, "", "true", "false"):
            return Response({"error": {"code": "invalid_active_filter"}}, status=400)
        if active_filter:
            queryset = queryset.filter(is_active=(active_filter == "true"))

        term = (request.query_params.get("search") or "").strip()
        if term:
            # Only account IDs are searchable here. Phone lookup would reveal customer identity
            # to staff without the dedicated PII permission and is intentionally not supported.
            if not term.isascii() or not term.isdecimal() or len(term) > 18:
                return Response({"error": {"code": "invalid_search"}}, status=400)
            queryset = queryset.filter(pk=int(term))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response([serialize_customer(row) for row in page])


@method_decorator(never_cache, name="dispatch")
class AdminCustomerDetailView(APIView):
    permission_classes = [StaffCustomerViewPermission]

    def get(self, request, customer_id):
        customer = get_object_or_404(customer_queryset(), pk=customer_id, is_staff=False, is_superuser=False)
        return Response(serialize_customer(customer))
