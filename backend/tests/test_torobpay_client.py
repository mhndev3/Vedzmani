import base64
import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.orders.torobpay import TorobPayClient, TorobPayError


@pytest.fixture(autouse=True)
def clear_torobpay_cache():
    cache.clear()
    yield
    cache.clear()


@override_settings(
    TOROBPAY_CLIENT_ID="client-id",
    TOROBPAY_CLIENT_SECRET="client-secret",
    TOROBPAY_USERNAME="merchant-user",
    TOROBPAY_PASSWORD="merchant-password",
)
def test_oauth_uses_basic_header_and_caches_jwt():
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, size): return b'{"access_token":"jwt-test"}'

    with patch("apps.orders.torobpay.urlopen", return_value=Response()) as send:
        client = TorobPayClient()
        assert client.access_token() == "jwt-test"
        assert client.access_token() == "jwt-test"
    assert send.call_count == 1
    request = send.call_args.args[0]
    expected = base64.b64encode(b"client-id:client-secret").decode("ascii")
    assert request.get_header("Authorization") == f"Basic {expected}"
    assert json.loads(request.data) == {
        "username": "merchant-user", "password": "merchant-password"
    }


@override_settings(
    TOROBPAY_CLIENT_ID="client-id",
    TOROBPAY_CLIENT_SECRET="client-secret",
    TOROBPAY_USERNAME="merchant-user",
    TOROBPAY_PASSWORD="merchant-password",
)
def test_eligibility_uses_bearer_and_rial_query_parameter():
    class OAuthResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, size): return b'{"access_token":"jwt-test"}'

    class ApiResponse:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, size):
            return b'{"successful":true,"response":{"eligible":true,"message_title":"Pay","description":"Credit"}}'

    with patch("apps.orders.torobpay.urlopen", side_effect=[OAuthResponse(), ApiResponse()]) as send:
        result = TorobPayClient().check_eligibility(250000)
    assert result["eligible"] is True
    request = send.call_args_list[1].args[0]
    assert request.get_header("Authorization") == "Bearer jwt-test"
    assert request.full_url.endswith("?amount=250000")


def test_eligibility_rejects_amounts_outside_documented_rial_range():
    with pytest.raises(TorobPayError, match="amount_out_of_range"):
        TorobPayClient().check_eligibility(199999)
    with pytest.raises(TorobPayError, match="amount_out_of_range"):
        TorobPayClient().check_eligibility(1_000_000_001)


@override_settings(
    TOROBPAY_CLIENT_ID="",
    TOROBPAY_CLIENT_SECRET="",
    TOROBPAY_USERNAME="",
    TOROBPAY_PASSWORD="",
)
def test_missing_credentials_fail_closed():
    with pytest.raises(TorobPayError, match="not_configured"):
        TorobPayClient().access_token()


@override_settings(
    TOROBPAY_CLIENT_ID="client-id",
    TOROBPAY_CLIENT_SECRET="client-secret",
    TOROBPAY_USERNAME="merchant-user",
    TOROBPAY_PASSWORD="merchant-password",
)
def test_provider_error_body_is_not_exposed_in_exception():
    from urllib.error import HTTPError
    error = HTTPError("https://provider.invalid", 403, "Forbidden", {}, None)
    with patch("apps.orders.torobpay.urlopen", side_effect=error):
        with pytest.raises(TorobPayError) as raised:
            TorobPayClient().access_token()
    assert raised.value.code == "provider_http_error"
    assert "password" not in str(raised.value).lower()
