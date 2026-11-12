"""Auth API. Django session authentication; CSRF is enforced on every POST."""

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, password_validation, update_session_auth_hash
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET
from rest_framework import status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .authentication import OTP_SESSION_FLAG
from .models import OTPChallenge
from .ratelimit import enforce_password_login, get_client_ip
from .serializers import (
    CurrentUserSerializer,
    CustomerProfileSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PasswordLoginSerializer,
    SetPasswordSerializer,
)

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



class PasswordLoginView(CSRFProtectedAPIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        enforce_password_login(get_client_ip(request), data["phone"])
        user = authenticate(request._request, phone=data["phone"], password=data["password"])
        if user is None or not user.is_active or user.is_staff:
            return Response(
                {"error": {"code": "invalid_credentials", "message": "Invalid phone or password."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request._request, user, backend=BACKEND)
        request._request.session.pop(OTP_SESSION_FLAG, None)
        request._request.session.set_expiry(0)
        return Response({"user": CurrentUserSerializer(user).data})


class SetPasswordView(CSRFProtectedAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.is_staff:
            return Response(
                {
                    "error": {
                        "code": "account_disabled",
                        "message": "Password change is unavailable for staff accounts.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        if not request._request.session.get(OTP_SESSION_FLAG):
            return Response(
                {
                    "error": {
                        "code": "otp_verification_required",
                        "message": "Verify your phone before setting a password.",
                    }
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        password = serializer.validated_data["password"]
        try:
            password_validation.validate_password(password, request.user)
        except DjangoValidationError as exc:
            raise ValidationError({"password": exc.messages}) from None
        request.user.set_password(password)
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request._request, request.user)
        request._request.session.pop(OTP_SESSION_FLAG, None)
        return Response({"detail": "Password set."})


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
        # Established by an SMS code only: valid for the customer API, refused by Django Admin (password required).
        django_request.session[OTP_SESSION_FLAG] = True
        # Deterministic remember-me: browser-session cookie vs. fixed lifetime.
        django_request.session.set_expiry(settings.AUTH_REMEMBER_ME_SECONDS if data["remember_me"] else 0)
        return Response({"user": CurrentUserSerializer(user).data, "is_new_user": created})


@method_decorator(never_cache, name="dispatch")  # personal data (phone): never cacheable
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


@method_decorator(never_cache, name="dispatch")
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CustomerProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = CustomerProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            # The database unique constraint closes the race between two simultaneous
            # profile updates that pass the serializer's preflight uniqueness query.
            raise ValidationError({
                "national_code": [ErrorDetail("این کد ملی قبلاً ثبت شده است.", code="unique")]
            }) from None
        return Response(serializer.data)
