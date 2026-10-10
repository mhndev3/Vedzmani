"""Orders API. Authentication = existing Django session auth (401 when anonymous, CSRF on POST).
The owner is always `request.user`; the request body and any client-supplied user id are ignored entirely."""

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Order
from .serializers import OrderSerializer


def _own_orders(user):
    """Every read goes through this queryset, so another user's order can never be reached (it simply 404s).
    Items are prefetched in one extra query; both orderings are explicit so the output is deterministic."""
    return Order.objects.filter(user=user).prefetch_related("items").order_by("-created_at", "-id")


@method_decorator(never_cache, name="dispatch")  # user-specific: never cached by browsers/proxies
class OrderListCreateView(APIView):
    def get(self, request):
        return Response(OrderSerializer(_own_orders(request.user), many=True).data)

    def post(self, request):
        order = services.create_order(request.user)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


@method_decorator(never_cache, name="dispatch")
class OrderDetailView(APIView):
    def get(self, request, order_id: int):
        order = get_object_or_404(_own_orders(request.user), pk=order_id)
        return Response(OrderSerializer(order).data)
