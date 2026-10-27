from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied

# Session key set by the customer OTP flow (views.OTPVerifyView). A session carrying it was established by
# possession of an SMS code, which is NOT enough to enter Django Admin (see admin_site.PasswordLoginAdminSite).
OTP_SESSION_FLAG = "auth_via_otp"


class CSRFFailed(PermissionDenied):
    """403 whose error-envelope code matches Django's CSRF failure view (`csrf_failed`)."""

    default_code = "csrf_failed"
    default_detail = "CSRF verification failed."


class SessionAuthentication401(SessionAuthentication):
    """Django session auth that answers 401 (not 403) when unauthenticated.
    CSRF is still enforced for authenticated unsafe requests; a failure is reported
    as `csrf_failed` (the reason is not echoed to the client)."""

    def authenticate_header(self, request):
        return "Session"

    def enforce_csrf(self, request):
        try:
            super().enforce_csrf(request)
        except PermissionDenied:
            raise CSRFFailed() from None
