"""Orders API. Authentication = existing Django session auth (401 when anonymous, CSRF on POST).
The owner is always request.user. Client input never controls order totals or payment state.
"""

from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Order
from .payment_services import PaymentRejected, initiate_sep_payment, process_sep_callback
from .serializers import CheckoutSerializer, OrderSerializer
from .torobpay_services import (
    check_torobpay_eligibility,
    initiate_torobpay_payment,
    process_torobpay_callback,
)


def _own_orders(user):
    """Every read goes through this queryset, so another user's order can never be reached."""
    return Order.objects.filter(user=user).prefetch_related("items").order_by("-created_at", "-id")


def _payment_error_response(exc):
    unavailable = {
        "payment_disabled", "payment_not_configured", "shipping_not_configured",
        "provider_unavailable", "not_configured", "disabled",
    }
    http_status = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if exc.code in unavailable
        else status.HTTP_409_CONFLICT
    )
    return Response({"error": {"code": exc.code}}, status=http_status)


@method_decorator(never_cache, name="dispatch")
class OrderListCreateView(APIView):
    def get(self, request):
        return Response(OrderSerializer(_own_orders(request.user), many=True).data)

    def post(self, request):
        if not settings.ORDERS_ENABLED:
            return Response(
                {"error": {"code": "orders_disabled", "message": "Order placement is temporarily disabled."}},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        details = CheckoutSerializer(data=request.data)
        details.is_valid(raise_exception=True)
        order = services.create_order(request.user, details.validated_data)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


@method_decorator(never_cache, name="dispatch")
class OrderDetailView(APIView):
    def get(self, request, order_id: int):
        order = get_object_or_404(_own_orders(request.user), pk=order_id)
        return Response(OrderSerializer(order).data)


class SepPaymentInitiateView(APIView):
    def post(self, request, order_id: int):
        order = get_object_or_404(_own_orders(request.user), pk=order_id)
        try:
            attempt = initiate_sep_payment(
                order, redirect_url=request.build_absolute_uri(reverse("sep-payment-callback-short"))
            )
        except PaymentRejected as exc:
            return _payment_error_response(exc)
        except Exception:
            return Response({"error": {"code": "payment_unavailable"}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({
            "payment_url": settings.SEP_PAYMENT_URL, "token": attempt.token,
            "res_num": attempt.res_num, "amount_rial": attempt.amount_rial,
        })


class TorobPayEligibilityView(APIView):
    def get(self, request, order_id: int):
        order = get_object_or_404(_own_orders(request.user), pk=order_id)
        try:
            result = check_torobpay_eligibility(order)
        except PaymentRejected as exc:
            return _payment_error_response(exc)
        return Response(result)


class TorobPayPaymentInitiateView(APIView):
    def post(self, request, order_id: int):
        order = get_object_or_404(_own_orders(request.user), pk=order_id)
        try:
            attempt = initiate_torobpay_payment(
                order,
                return_url=request.build_absolute_uri(reverse("torobpay-payment-callback")),
            )
        except PaymentRejected as exc:
            return _payment_error_response(exc)
        except Exception:
            return Response({"error": {"code": "payment_unavailable"}}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({
            "payment_url": attempt.payment_page_url,
            "transaction_id": str(attempt.merchant_transaction_id),
            "amount_rial": attempt.amount_rial,
        })


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class SepPaymentCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ready"})

    def post(self, request):
        result = process_sep_callback(
            res_num=str(request.data.get("ResNum") or ""),
            ref_num=str(request.data.get("RefNum") or ""),
        )
        page_status = "success" if result == "paid" else "pending" if result == "pending" else "failed"
        return HttpResponseRedirect(f"/fa/checkout/payment-result?status={page_status}")


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class TorobPayPaymentCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        # Non-mutating reachability probe only.
        return Response({"status": "ready"})

    def post(self, request):
        result = process_torobpay_callback(
            transaction_id=str(request.data.get("transactionId") or ""),
            state=str(request.data.get("state") or "").upper(),
            amount=str(request.data.get("amount") or ""),
        )
        page_status = "success" if result == "paid" else "pending" if result == "pending" else "failed"
        return HttpResponseRedirect(f"/fa/checkout/payment-result?status={page_status}")
