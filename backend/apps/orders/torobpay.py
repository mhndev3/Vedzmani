""""Server-side TorobPay CPG API client.

Credentials and JWTs never leave the backend. Provider responses are validated
against the documented envelope; error bodies and secrets are never logged.
"""
import base64
import hashlib
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.core.cache import cache


class TorobPayError(Exception):
    """A safe, non-sensitive provider/API failure."""

    def __init__(self, code="provider_error", http_status=None):
        self.code = code
        self.http_status = http_status
        super().__init__(code)


class TorobPayUnavailable(TorobPayError):
    """The provider did not return a usable response."""


class TorobPayClient:
    TOKEN_CACHE_SECONDS = 55 * 60

    def __init__(self):
        self.base_url = settings.TOROBPAY_BASE_URL.rstrip("/")

    def _credentials(self, *, allow_when_disabled=False):
        # The explicit exception is used only by the OAuth-only management command.
        # Normal payment API calls remain blocked by TOROBPAY_ENABLED.
        if not settings.TOROBPAY_ENABLED and not allow_when_disabled:
            raise TorobPayError("disabled")
        values = (
            settings.TOROBPAY_CLIENT_ID,
            settings.TOROBPAY_CLIENT_SECRET,
            settings.TOROBPAY_USERNAME,
            settings.TOROBPAY_PASSWORD,
        )
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise TorobPayError("not_configured")
        return values

    def _url(self, path):
        if not path.startswith("/") or path.startswith("//"):
            raise TorobPayError("invalid_endpoint")
        return f"{self.base_url}{path}"

    def _send(self, method, path, *, payload=None, bearer=None, basic=None, query=None):
        url = self._url(path)
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        if basic:
            headers["Authorization"] = f"Basic {basic}"
        body = None if payload is None else json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=settings.TOROBPAY_TIMEOUT_SECONDS) as response:
                raw = response.read(65536)
                http_status = response.status
        except HTTPError as exc:
            # Do not surface provider response bodies: they may contain account data.
            raise TorobPayError("provider_http_error", http_status=exc.code) from exc
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise TorobPayUnavailable("provider_unavailable") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TorobPayError("invalid_provider_json", http_status=http_status) from exc
        if not isinstance(data, dict):
            raise TorobPayError("invalid_provider_response", http_status=http_status)
        return data, http_status

    def access_token(self, *, force_refresh=False, allow_when_disabled=False):
        client_id, client_secret, username, password = self._credentials(
            allow_when_disabled=allow_when_disabled
        )
        cache_digest = hashlib.sha256(f"{client_id}:{client_secret}".encode("utf-8")).hexdigest()[:24]
        cache_key = f"torobpay:jwt:{cache_digest}"
        if not force_refresh:
            cached = cache.get(cache_key)
            if isinstance(cached, str) and cached:
                return cached
        basic_value = base64.b64encode(
            f"{client_id}:{client_secret}".encode("utf-8")
        ).decode("ascii")
        data, http_status = self._send(
            "POST",
            "/api/online/v1/oauth/token",
            payload={"username": username, "password": password},
            basic=basic_value,
        )
        token = data.get("access_token")
        if http_status < 200 or http_status >= 300 or not isinstance(token, str) or not token.strip():
            raise TorobPayError("token_rejected", http_status=http_status)
        cache.set(cache_key, token, self.TOKEN_CACHE_SECONDS)
        return token

    def check_connection(self):
        """Perform only a fresh OAuth request; never call payment or eligibility APIs."""
        self.access_token(force_refresh=True, allow_when_disabled=True)
        return True

    def _api(self, method, path, *, payload=None, query=None):
        token = self.access_token()
        data, http_status = self._send(
            method, path, payload=payload, query=query, bearer=token
        )
        if http_status < 200 or http_status >= 300 or data.get("successful") is not True:
            error = data.get("error")
            code = error.get("code") if isinstance(error, dict) else None
            safe_code = str(code)[:64] if isinstance(code, (str, int)) else "provider_rejected"
            raise TorobPayError(safe_code, http_status=http_status)
        response = data.get("response")
        if not isinstance(response, dict):
            raise TorobPayError("invalid_provider_response", http_status=http_status)
        return response

    def check_eligibility(self, amount_rial):
        if isinstance(amount_rial, bool) or not isinstance(amount_rial, int):
            raise TorobPayError("invalid_amount")
        if amount_rial < 200_000 or amount_rial > 1_000_000_000:
            raise TorobPayError("amount_out_of_range")
        response = self._api(
            "GET", "/api/online/offer/v1/eligible", query={"amount": amount_rial}
        )
        eligible = response.get("eligible")
        if not isinstance(eligible, bool):
            raise TorobPayError("invalid_eligibility_response")
        return response

    def create_payment_token(self, payload):
        if not isinstance(payload, dict):
            raise TorobPayError("invalid_payment_payload")
        response = self._api(
            "POST", "/api/online/payment/v1/token", payload=payload
        )
        if not all(
            isinstance(response.get(key), str) and response[key].strip()
            for key in ("paymentToken", "paymentPageUrl")
        ):
            raise TorobPayError("invalid_payment_token_response")
        page_url = urlsplit(response["paymentPageUrl"])
        if page_url.scheme != "https" or not page_url.hostname or page_url.username or page_url.password:
            raise TorobPayError("invalid_payment_page_url")
        return response

    def verify(self, payment_token):
        return self._payment_action("verify", payment_token)

    def settle(self, payment_token):
        return self._payment_action("settle", payment_token)

    def revert(self, payment_token):
        return self._payment_action("revert", payment_token)

    def status(self, payment_token):
        if not isinstance(payment_token, str) or not payment_token.strip():
            raise TorobPayError("invalid_payment_token")
        return self._api(
            "GET", "/api/online/payment/v1/status",
            query={"paymentToken": payment_token},
        )

    def cancel(self, payment_token):
        return self._payment_action("cancel", payment_token)

    def update(self, payload):
        if not isinstance(payload, dict):
            raise TorobPayError("invalid_update_payload")
        return self._api(
            "POST", "/api/online/payment/v1/update", payload=payload
        )

    def _payment_action(self, action, payment_token):
        if not isinstance(payment_token, str) or not payment_token.strip():
            raise TorobPayError("invalid_payment_token")
        return self._api(
            "POST",
            f"/api/online/payment/v1/{action}",
            payload={"paymentToken": payment_token},
        )
