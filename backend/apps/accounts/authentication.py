from rest_framework.authentication import SessionAuthentication


class SessionAuthentication401(SessionAuthentication):
    """Django session auth that answers 401 (not 403) when unauthenticated.
    CSRF is still enforced for authenticated unsafe requests."""

    def authenticate_header(self, request):
        return "Session"
