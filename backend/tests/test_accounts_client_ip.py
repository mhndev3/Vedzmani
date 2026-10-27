"""Client-IP derivation (apps/accounts/ratelimit.get_client_ip) and what it means for the per-IP rate limits.

Topologies modelled (taken from the repo's nginx configs, nothing assumed beyond them):
  * nginx/default.conf (main):  X-Forwarded-For = $proxy_add_x_forwarded_for  -> client-supplied entries are KEPT and
    Nginx APPENDS the address it sees as the last entry.
  * nginx/prod.conf (infra branch): X-Forwarded-For = $remote_addr -> the header is OVERWRITTEN with the address Nginx
    sees (the real client once cloudflare-realip.conf lists the Cloudflare ranges, a Cloudflare edge address before).
In both, AUTH_TRUSTED_PROXY_COUNT=1 means "take the LAST entry", which is the one our own Nginx wrote.

These are unit/HTTP tests of Django's side only. They do NOT prove what Nginx or Cloudflare do in production."""

import json

import pytest

from apps.accounts.ratelimit import get_client_ip

pytestmark = pytest.mark.django_db

PEER = "172.18.0.9"  # the Nginx container as Django sees it (REMOTE_ADDR)


@pytest.fixture
def one_proxy(settings):
    settings.AUTH_TRUSTED_PROXY_COUNT = 1


def ip_of(rf, xff=None, remote=PEER):
    extra = {"REMOTE_ADDR": remote}
    if xff is not None:
        extra["HTTP_X_FORWARDED_FOR"] = xff
    return get_client_ip(rf.get("/", **extra))


# ------------------------------------------------------------- trust chain --
def test_without_trusted_proxies_forwarded_for_is_ignored(rf, settings):
    settings.AUTH_TRUSTED_PROXY_COUNT = 0
    assert ip_of(rf, "9.9.9.9, 203.0.113.7") == PEER


def test_nginx_append_topology_a_client_cannot_pick_its_identity(rf, one_proxy):
    # client sent "X-Forwarded-For: 9.9.9.9, 8.8.8.8"; Nginx appended the address it saw
    assert ip_of(rf, "9.9.9.9, 8.8.8.8, 203.0.113.7") == "203.0.113.7"


def test_nginx_overwrite_topology_yields_the_single_entry(rf, one_proxy):
    assert ip_of(rf, "203.0.113.7") == "203.0.113.7"


@pytest.mark.parametrize("xff", [None, "", " , ,"])
def test_missing_or_empty_forwarded_for_falls_back_to_the_peer_address(rf, one_proxy, xff):
    assert ip_of(rf, xff) == PEER


def test_fewer_entries_than_trusted_hops_falls_back_to_the_peer_address(rf, settings):
    settings.AUTH_TRUSTED_PROXY_COUNT = 3
    assert ip_of(rf, "203.0.113.7") == PEER


@pytest.mark.parametrize("garbage", ["not-an-ip", "x" * 500, "203.0.113.7:8080", "999.1.1.1", "'; DROP TABLE--"])
def test_a_rightmost_entry_that_is_not_an_ip_is_never_used_as_identity(rf, one_proxy, garbage):
    assert ip_of(rf, f"203.0.113.7, {garbage}") == PEER


def test_unusable_peer_address_yields_a_constant_identity(rf, settings):
    settings.AUTH_TRUSTED_PROXY_COUNT = 0
    assert ip_of(rf, remote="") == "unknown"
    assert ip_of(rf, remote="garbage") == "unknown"


# --------------------------------------------------------------- canonical --
def test_ipv6_addresses_of_one_slash_64_share_one_identity(rf, one_proxy):
    first = ip_of(rf, "2001:db8:aaaa:bbbb::1")
    second = ip_of(rf, "2001:db8:aaaa:bbbb:ffff:ffff:ffff:ffff")
    other_prefix = ip_of(rf, "2001:db8:aaaa:cccc::1")
    assert first == second and first != other_prefix


def test_ipv4_identity_is_unchanged_and_mapped_ipv6_equals_plain_ipv4(rf, one_proxy):
    assert ip_of(rf, "203.0.113.7") == "203.0.113.7"
    assert ip_of(rf, "::ffff:203.0.113.7") == "203.0.113.7"


# ------------------------------------------------- limit implications (HTTP) --
def _post(api, path, body, *, xff, remote=PEER):
    return api.client.post(
        path,
        data=json.dumps(body),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=api._token(),
        HTTP_X_FORWARDED_FOR=xff,
        REMOTE_ADDR=remote,
    )


def test_rotating_a_spoofed_prefix_does_not_buy_new_otp_request_buckets(api, settings, one_proxy):
    settings.OTP_REQUEST_COOLDOWN_SECONDS = 0
    settings.OTP_REQUEST_IP_LIMIT = 2
    statuses = [
        _post(api, "/api/auth/otp/request/", {"phone": f"0912000000{i}"}, xff=f"10.0.0.{i}, 203.0.113.7").status_code
        for i in range(4)
    ]
    assert statuses == [202, 202, 429, 429]  # same last entry -> same bucket, whatever the client prepended
    other_client = _post(api, "/api/auth/otp/request/", {"phone": "09120000099"}, xff="198.51.100.20")
    assert other_client.status_code == 202  # a genuinely different address has its own bucket


def test_known_limitation_a_direct_hit_that_bypasses_nginx_chooses_its_own_identity(api, settings, one_proxy):
    """DOCUMENTS A LIMITATION, not desired behavior. With AUTH_TRUSTED_PROXY_COUNT=1 the backend believes the last
    X-Forwarded-For entry. That is only safe while the backend is reachable exclusively through Nginx (no published
    port, no other container/host that can reach it). Closing it in code would need a trusted-proxy CIDR setting
    (owner/infra decision). Update this test when such a setting exists."""
    settings.OTP_REQUEST_COOLDOWN_SECONDS = 0
    settings.OTP_REQUEST_IP_LIMIT = 1
    statuses = [
        _post(api, "/api/auth/otp/request/", {"phone": f"0912111111{i}"}, xff=f"198.51.100.{i}", remote="203.0.113.50").status_code
        for i in range(3)
    ]
    assert statuses == [202, 202, 202]  # the per-IP limit never triggers: each request claims a new "client"


def test_users_behind_one_unresolved_edge_address_share_one_verify_budget(api, settings, one_proxy):
    """Implication of Nginx seeing only a Cloudflare edge address (cloudflare-realip.conf empty / default.conf):
    every user routed through that edge is ONE client to the limiter, so one abuser can exhaust the verify budget of
    the others. Safe against spoofing, but an availability risk until real client IPs reach Nginx."""
    settings.OTP_VERIFY_IP_LIMIT = 3
    edge = "104.16.0.1"
    abuser = [_post(api, "/api/auth/otp/verify/", {"phone": "09121234567", "code": "000000"}, xff=edge).status_code for _ in range(4)]
    assert abuser[-1] == 429
    innocent = _post(api, "/api/auth/otp/verify/", {"phone": "09127654321", "code": "000000"}, xff=edge)
    assert innocent.status_code == 429  # a different real user, same edge address
