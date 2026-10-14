"""E2E-only helper for the checkout tests (NOT production code).

Run against a THROWAWAY database only, from the backend directory:

  cd backend
  E2E_ACTION=session E2E_PHONE=09120000001 python manage.py shell -c "exec(open('../e2e/e2e_helper.py', encoding='utf-8').read())"

(Use `-c exec(...)`, not `< file`: piped stdin is not executed on Windows and fails silently.)

Why it exists: production sign-in needs an SMS provider that does not exist yet, so a test
cannot complete the real OTP flow. This creates a real user and a real server-side Django
session through Django's own `force_login` (the same session store `login()` writes to). The
browser then presents that cookie exactly as it would a real login cookie. Everything after
that (cart, CSRF, checkout, order creation) goes through the real API with no bypass.

Actions (E2E_ACTION):
  session    create/get the user for E2E_PHONE and return a sessionid + variant-size ids
  set_stock  set VariantSize.stock_quantity for E2E_SKU to E2E_STOCK (simulates stock changing
             after an item is already in a cart; the cart API itself refuses over-stock adds)
"""

import json
import os

from django.test import Client

from apps.accounts.models import User
from apps.catalog.models import VariantSize

action = os.environ["E2E_ACTION"]

if action == "session":
    user, _created = User.objects.get_or_create_by_phone(os.environ["E2E_PHONE"])
    client = Client()
    client.force_login(user)
    out = {
        "sessionid": client.cookies["sessionid"].value,
        "phone": user.phone,
        "variantSizeIds": dict(VariantSize.objects.values_list("sku", "id")),
    }
elif action == "set_stock":
    updated = VariantSize.objects.filter(sku=os.environ["E2E_SKU"]).update(
        stock_quantity=int(os.environ["E2E_STOCK"])
    )
    out = {"updated": updated}
else:
    raise SystemExit(f"unknown E2E_ACTION: {action}")

print("E2E_JSON:" + json.dumps(out))
