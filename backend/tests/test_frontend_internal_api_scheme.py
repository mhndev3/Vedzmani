"""Static guard for the server-side API client's forwarded-scheme header (no Docker, network or database).

Production TLS ends at Nginx; Django (SECURE_SSL_REDIRECT=True) answers any plain-HTTP request that lacks
`X-Forwarded-Proto: https` with a 301 to https://backend:8000, which the Next.js server cannot reach (about ten seconds
of connect timeout on /fa/products). The Django side of that contract is pinned in test_production_proxy_behavior.py;
this file pins the frontend side and the trust boundary around it:

* `apiGet` (server-only, talks to the internal backend URL) sends `X-Forwarded-Proto: https`.
* `apiGet` cannot be bundled into browser code (`import "server-only"`), and no Client Component imports it or
  `catalog.ts`, so browsers never run this code path.
* The browser-side fetch helpers never set `X-Forwarded-Proto`; for external traffic Nginx alone decides the scheme.

It reads repository files only. It does not replace running the production-like stack.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "frontend" / "src"
API_TS = SRC / "lib" / "api.ts"
BROWSER_HELPERS = (SRC / "lib" / "browser-api.ts", SRC / "lib" / "checkout" / "api.ts")

pytestmark = pytest.mark.skipif(
    not API_TS.is_file(),
    reason="frontend sources are not available (backend tests run outside a full checkout)",
)

HEADER = re.compile(r"""["']X-Forwarded-Proto["']\s*:\s*["']https["']""", re.IGNORECASE)
SERVER_ONLY = re.compile(r"""^\s*import\s+["']server-only["'];?\s*$""", re.MULTILINE)
# Imports of the server-only modules via the alias or a relative path (lib/api, lib/catalog, ./api, ./catalog).
SERVER_MODULE_IMPORT = re.compile(
    r"""from\s+["'](?:@/lib/(?:api|catalog)|\.{1,2}/(?:lib/)?(?:api|catalog))["']"""
)


def test_internal_api_client_sends_forwarded_https_scheme():
    assert HEADER.search(API_TS.read_text(encoding="utf-8")), (
        "apiGet must send X-Forwarded-Proto: https, otherwise Django redirects internal HTTP calls to an "
        "unreachable https://backend:8000 and server-rendered pages stall until the connect timeout"
    )


def test_internal_api_client_is_server_only():
    assert SERVER_ONLY.search(API_TS.read_text(encoding="utf-8")), (
        'api.ts must keep `import "server-only"` so the internal-proxy header can never ship in browser code'
    )


def test_no_client_component_imports_the_server_only_api_modules():
    offenders = []
    for path in list(SRC.rglob("*.ts")) + list(SRC.rglob("*.tsx")):
        text = path.read_text(encoding="utf-8")
        is_client = re.match(r"""\s*(?:/\*.*?\*/\s*|//[^\n]*\n\s*)*["']use client["']""", text, re.DOTALL)
        if is_client and SERVER_MODULE_IMPORT.search(text):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"Client Components must not import the server-only API modules: {offenders}"


@pytest.mark.parametrize("path", BROWSER_HELPERS, ids=lambda p: p.name)
def test_browser_side_helpers_do_not_set_the_forwarded_scheme(path):
    assert path.is_file(), f"expected browser helper {path.relative_to(REPO_ROOT)}"
    assert "x-forwarded-proto" not in path.read_text(encoding="utf-8").lower(), (
        "browsers must not send proxy headers; Nginx sets X-Forwarded-Proto itself for external traffic"
    )
