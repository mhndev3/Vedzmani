"""Orders API. Authentication = existing Django session auth (401 when anonymous, CSRF on POST).
The owner is always `request.user`; the request body is ignored entirely."""

from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import OrderSerializer


@method_decorator(never_cache, name="dispatch")  # user-specific: never cached by browsers/proxies
class OrderCreateView(APIView):
    def post(self, request):
        order = services.create_order(request.user)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
