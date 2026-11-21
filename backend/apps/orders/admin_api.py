"""Read-only staff order API for the custom admin workspace.

Order lifecycle mutations are intentionally absent: cancellation, refunds, delivery transitions and stock
restoration need a separately reviewed business workflow. Customer PII is independently permission-gated.
"""
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import serializers

from .models import Order, OrderItem
from .permissions import has_order_pii_permission, mask_phone


class StaffOrderViewPermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_active and user.is_staff
            and user.has_perm("orders.view_order")
        )


class AdminOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id", "variant_size_id", "product_name", "color_name", "size_label",
            "sku", "unit_price", "quantity", "subtotal",
        )


class AdminOrderSerializer(serializers.ModelSerializer):
    items = AdminOrderItemSerializer(many=True, read_only=True)
    customer_phone = serializers.SerializerMethodField()
    pii_hidden = serializers.SerializerMethodField()
    recipient_name = serializers.SerializerMethodField()
    province = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    postal_code = serializers.SerializerMethodField()
    customer_account_id = serializers.IntegerField(source="user_id", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id", "status", "payment_status", "customer_phone", "customer_account_id",
            "recipient_name", "province", "city", "address", "postal_code", "pii_hidden",
            "total", "created_at", "updated_at", "items",
        )

    def _can_view_pii(self, obj):
        request = self.context["request"]
        return has_order_pii_permission(request.user)

    def get_customer_phone(self, obj):
        return obj.customer_phone if self._can_view_pii(obj) else mask_phone(obj.customer_phone)

    def get_pii_hidden(self, obj):
        return not self._can_view_pii(obj)

    def _pii(self, obj, field):
        return getattr(obj, field) if self._can_view_pii(obj) else ""

    def get_recipient_name(self, obj):
        return self._pii(obj, "recipient_name")

    def get_province(self, obj):
        return self._pii(obj, "province")

    def get_city(self, obj):
        return self._pii(obj, "city")

    def get_address(self, obj):
        return self._pii(obj, "address")

    def get_postal_code(self, obj):
        return self._pii(obj, "postal_code")


class AdminOrderPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50


class AdminOrderListView(APIView):
    permission_classes = [StaffOrderViewPermission]
    pagination_class = AdminOrderPagination

    def get(self, request):
        queryset = Order.objects.select_related("user").prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.order_by("id"))
        ).order_by("-created_at", "-id")

        status_filter = request.query_params.get("status")
        if status_filter:
            valid = {value for value, _ in Order.STATUS_CHOICES}
            if status_filter not in valid:
                return Response({"error": {"code": "invalid_status"}}, status=400)
            queryset = queryset.filter(status=status_filter)

        payment_filter = request.query_params.get("payment_status")
        if payment_filter:
            valid = {value for value, _ in Order.PAYMENT_STATUS_CHOICES}
            if payment_filter not in valid:
                return Response({"error": {"code": "invalid_payment_status"}}, status=400)
            queryset = queryset.filter(payment_status=payment_filter)

        term = (request.query_params.get("search") or "").strip()
        if term:
            condition = Q(items__sku__icontains=term) | Q(items__product_name__icontains=term)
            if term.isascii() and term.isdecimal() and len(term) <= 18:
                condition |= Q(pk=int(term))
            queryset = queryset.filter(condition).distinct()

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminOrderSerializer(page, many=True, context={"request": request})
        return paginator.get_paginated_response(serializer.data)


class AdminOrderDetailView(APIView):
    permission_classes = [StaffOrderViewPermission]

    def get(self, request, order_id):
        order = get_object_or_404(
            Order.objects.select_related("user").prefetch_related(
                Prefetch("items", queryset=OrderItem.objects.order_by("id"))
            ),
            pk=order_id,
        )
        return Response(AdminOrderSerializer(order, context={"request": request}).data)
