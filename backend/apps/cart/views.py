"""Cart API; all cart state and ownership are bound to the authenticated session user."""
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import AddItemSerializer, CartSerializer, GuestCartMergeSerializer, UpdateItemSerializer


def cart_response(user, http_status=status.HTTP_200_OK) -> Response:
    return Response(CartSerializer(services.build_cart(user)).data, status=http_status)


@method_decorator(never_cache, name="dispatch")
class CartView(APIView):
    def get(self, request):
        return cart_response(request.user)

    def delete(self, request):
        services.clear_cart(request.user)
        return cart_response(request.user)


@method_decorator(never_cache, name="dispatch")
class CartItemListView(APIView):
    def post(self, request):
        data = AddItemSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.add_item(request.user, **data.validated_data)
        return cart_response(request.user, status.HTTP_201_CREATED)


@method_decorator(never_cache, name="dispatch")
class CartItemDetailView(APIView):
    def patch(self, request, item_id: int):
        data = UpdateItemSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.set_item_quantity(request.user, item_id, data.validated_data["quantity"])
        return cart_response(request.user)

    def delete(self, request, item_id: int):
        services.remove_item(request.user, item_id)
        return cart_response(request.user)


@method_decorator(never_cache, name="dispatch")
class GuestCartMergeView(APIView):
    """Authenticated-only merge; user, prices, stock and catalog state are never client supplied."""
    def post(self, request):
        data = GuestCartMergeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        services.merge_guest_items(request.user, **data.validated_data)
        return cart_response(request.user)
