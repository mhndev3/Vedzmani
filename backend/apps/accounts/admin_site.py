"""Django Admin site that refuses sessions established only by the customer OTP flow.

Why: the OTP flow creates an ordinary Django session. Django Admin accepts any active ``is_staff`` session, so
without this gate possession of an SMS code (SIM swap, provider compromise, interception) would open the admin for
a staff phone and the staff password (documented in ADMIN.md) would be bypassed.

How: ``OTPVerifyView`` flags its session (``OTP_SESSION_FLAG``). This site denies flagged sessions and clears the
flag when the user then succeeds at the admin's own password form. Sessions created any other way (admin password
login, ``force_login`` in tests) carry no flag and behave exactly as before. The customer API is unaffected.
"""

from django.contrib.admin import AdminSite

from .authentication import OTP_SESSION_FLAG


class PasswordLoginAdminSite(AdminSite):
    def has_permission(self, request):
        if request.session.get(OTP_SESSION_FLAG):
            return False
        return super().has_permission(request)

    def login(self, request, extra_context=None):
        response = super().login(request, extra_context)
        # A redirect after POST means the admin password form accepted the credentials (an invalid form re-renders
        # with 200), so this session now rests on the password and the OTP-only restriction no longer applies.
        if request.method == "POST" and response.status_code == 302 and request.user.is_authenticated:
            request.session.pop(OTP_SESSION_FLAG, None)
        return response
