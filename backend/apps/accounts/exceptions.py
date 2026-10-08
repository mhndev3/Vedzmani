"""Auth API errors. Rendered as {"error": {"code", "message"}} by
apps.core.exceptions.api_exception_handler."""

from rest_framework import status
from rest_framework.exceptions import APIException, Throttled


class RateLimited(Throttled):
    default_code = "rate_limited"
    default_detail = "Too many requests. Please try again later."


class OTPError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST


class OTPInvalid(OTPError):
    default_code = "otp_invalid"
    default_detail = "The verification code is incorrect."


class OTPExpired(OTPError):
    default_code = "otp_expired"
    default_detail = "The verification code has expired. Request a new one."


class OTPConsumed(OTPError):
    default_code = "otp_consumed"
    default_detail = "This verification code has already been used."


class OTPAttemptsExceeded(OTPError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "otp_attempts_exceeded"
    default_detail = "Too many incorrect attempts. Request a new code."


class AccountDisabled(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "account_disabled"
    default_detail = "This account is disabled."


class DeliveryUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_code = "otp_delivery_unavailable"
    default_detail = "Verification codes cannot be sent right now."
