"""Auth API. Django session authentication; CSRF is enforced on every POST."""

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import OTPChallenge
from .ratelimit import get_client_ip
from .serializers import CurrentUserSerializer, OTPRequestSerializer, OTPVerifySerializer

BACKEND = "django.contrib.auth.backends.ModelBackend"


@require_GET
@never_cache
@ensure_csrf_cookie
def csrf(request):
    """Sets the csrftoken cookie and returns the token. Clients call this once
    before their first POST and send it back as the X-CSRFToken header."""
    return JsonResponse({"csrfToken": get_token(request)})


class CSRFProtectedAPIView(APIView):
    """DRF views are csrf_exempt by default, and DRF only checks CSRF for
    already-authenticated users - which would leave login itself open to
    login-CSRF. Re-apply Django's CSRF protection to every request."""

    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class OTPRequestView(CSRFProtectedAPIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.request_otp(
            phone=serializer.validated_data["phone"],
            purpose=OTPChallenge.Purpose.LOGIN,
            ip=get_client_ip(request),
        )
        # Identical for every phone: reveals nothing about account existence.
        return Response({"detail": "OTP request accepted."}, status=status.HTTP_202_ACCEPTED)


class OTPVerifyView(CSRFProtectedAPIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user, created = services.verify_otp(
            phone=data["phone"],
            purpose=OTPChallenge.Purpose.LOGIN,
            code=data["code"],
            ip=get_client_ip(request),
        )
        django_request = request._request
        login(django_request, user, backend=BACKEND)  # rotates the session key
        # Deterministic remember-me: browser-session cookie vs. fixed lifetime.
        django_request.session.set_expiry(settings.AUTH_REMEMBER_ME_SECONDS if data["remember_me"] else 0)
        return Response({"user": CurrentUserSerializer(user).data, "is_new_user": created})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class LogoutView(CSRFProtectedAPIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]  # idempotent: logging out twice is fine

    def post(self, request):
        logout(request._request)  # flushes the server-side session row
        return Response(status=status.HTTP_204_NO_CONTENT)
