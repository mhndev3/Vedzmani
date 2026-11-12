"""SEP OnlinePG client for the classic token-based protocol."""
import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from django.conf import settings

class SepError(Exception):
    pass

class SepUnavailable(SepError):
    pass

class SepClient:
    def _post(self, url, payload):
        request = Request(url, data=json.dumps(payload, separators=(",", ":")).encode(),
                          headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=settings.SEP_TIMEOUT_SECONDS) as response:
                raw = response.read(65536)
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise SepUnavailable("SEP did not return a response.") from exc
        except HTTPError as exc:
            raise SepError(f"SEP returned HTTP {exc.code}.") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SepError("SEP returned an invalid response.") from exc
        if not isinstance(data, dict):
            raise SepError("SEP returned an invalid response.")
        return data

    def _terminal(self):
        if not settings.SEP_TERMINAL_ID:
            raise SepError("SEP terminal is not configured.")
        return settings.SEP_TERMINAL_ID

    def request_token(self, *, amount_rial, res_num, redirect_url, cell_number):
        result = self._post(settings.SEP_TOKEN_URL, {
            "action": "token", "TerminalId": self._terminal(), "Amount": amount_rial,
            "ResNum": res_num, "RedirectUrl": redirect_url, "CellNumber": cell_number,
            "TokenExpiryInMin": 20,
        })
        token = result.get("token")
        if result.get("status") != 1 or not isinstance(token, str) or not token:
            raise SepError("SEP could not create a payment token.")
        return token

    def verify(self, ref_num):
        payload = {"RefNum": ref_num, "TerminalNumber": int(self._terminal())}
        last_error = None
        for attempt in range(3):
            try:
                return self._post(settings.SEP_VERIFY_URL, payload)
            except SepUnavailable as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
        raise last_error

    def reverse(self, ref_num):
        return self._post(settings.SEP_REVERSE_URL, {
            "RefNum": ref_num, "TerminalNumber": int(self._terminal())
        })
