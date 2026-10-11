"""Orders API. Authentication = existing Django session auth (401 when anonymous, CSRF on POST).
The owner is always `request.user`. The only client input to order creation is the Iranian delivery details
(`CheckoutSerializer`); any other key in the body (user id, total, status, payment status, phone, ...) is ignored."""

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Order
from .serializers import CheckoutSerializer, OrderSerializer


def _own_orders(user):
    """Every read goes through this queryset, so another user's order can never be reached (it simply 404s).
    Items are prefetched in one extra query; both orderings are explicit so the output is deterministic."""
    return Order.objects.filter(user=user).prefetch_related("items").order_by("-created_at", "-id")


@method_decorator(never_cache, name="dispatch")  # user-specific: never cached by browsers/proxies
class OrderListCreateView(APIView):
    def get(self, request):
        return Response(OrderSerializer(_own_orders(request.user), many=True).data)

    def post(self, request):
        # Validate BEFORE the transaction: invalid delivery details take no lock and change nothing
        # (no order, no stock change, cart untouched). Authentication and CSRF were already enforced by DRF.
        details = CheckoutSerializer(data=request.data)
        details.is_valid(raise_exception=True)
        order = services.create_order(request.user, details.validated_data)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


@method_decorator(never_cache, name="dispatch")
class OrderDetailView(APIView):
    def get(self, request, order_id: int):
        order = get_object_or_404(_own_orders(request.user), pk=order_id)
        return Response(OrderSerializer(order).data)
