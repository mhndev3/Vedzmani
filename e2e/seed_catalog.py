"""E2E-only fixture data for the catalog tests (NOT production data).

Run against a throwaway database, never the real one. It refuses to run unless E2E_THROWAWAY_DB=1 is set
(your confirmation that the database is disposable; see the guard below). It creates ACTIVE products with
stock, which would appear on a real storefront:
  cd backend; E2E_THROWAWAY_DB=1 DATABASE_URL=postgres://.../vedzmani_e2e python manage.py shell -c "exec(open('../e2e/seed_catalog.py', encoding='utf-8').read())"
Idempotent: skips if the fixture products already exist.
"""

import os
from decimal import Decimal

# --- Safety guard (runs before any database access) -------------------------------------------------
# This script writes to whatever database DATABASE_URL points at. E2E_THROWAWAY_DB=1 is the OPERATOR'S
# CONFIRMATION that it is disposable; it cannot verify that, and it does not make a real database safe.
# The settings check only rejects an obviously wrong configuration (production). It never prints
# DATABASE_URL, which can contain a password.
from django.conf import settings  # noqa: E402

if os.environ.get("E2E_THROWAWAY_DB") != "1":
    raise SystemExit(
        "refusing to run: set E2E_THROWAWAY_DB=1 to confirm DATABASE_URL points at a disposable test "
        "database (never a development, staging or production one)"
    )
if settings.SETTINGS_MODULE not in ("config.settings.dev", "config.settings.test"):
    raise SystemExit(f"refusing to run with settings module {settings.SETTINGS_MODULE!r}")
# -----------------------------------------------------------------------------------------------------

from apps.catalog.models import (
    Category,
    Collection,
    ColorVariant,
    Product,
    Size,
    VariantImage,
    VariantSize,
)

if not Product.objects.filter(slug="e2e-hoodie-01").exists():
    sizes = {c: Size.objects.get_or_create(code=c, defaults={"label": c.upper(), "position": i})[0] for i, c in enumerate(["s", "m", "l"])}
    hoodies = Category.objects.get_or_create(slug="hoodies", defaults={"name": "Hoodies", "position": 1})[0]
    tees = Category.objects.get_or_create(slug="tees", defaults={"name": "Tees", "position": 2})[0]
    winter = Collection.objects.get_or_create(slug="winter", defaults={"name": "Winter"})[0]

    def make(n, category, label):
        p = Product.objects.create(
            category=category,
            name=f"{label} {n:02d}",
            slug=f"e2e-{label.lower()}-{n:02d}",
            description=f"Fixture {label} number {n}.\nSecond line.",
            price=Decimal(1000 * n + (500 if label == "Hoodie" else 0)),
            sale_price=Decimal(900 * n) if (label == "Hoodie" and n == 2) else None,
            is_active=True,
        )
        if label == "Hoodie":
            p.collections.add(winter)
        for pos, (slug, name, hexc) in enumerate([("black", "Black", "#111111"), ("white", "White", "#f5f5f5")]):
            v = ColorVariant.objects.create(product=p, name=name, slug=slug, hex_color=hexc, position=pos)
            VariantImage.objects.create(
                variant=v,
                storage_key=f"e2e/{p.slug}-{slug}.webp",
                alt_text=f"{p.name} {name}",
                position=0,
                is_primary=True,
                width=600,
                height=800,
            )
            for code, size in sizes.items():
                # Hoodie 03 is entirely out of stock; Hoodie 01 white is out of stock only.
                # Tee 15 black has exactly one sold-out size (L), so product-detail.spec.ts can check a
                # partially available color. It does not change any product's overall in-stock status.
                sold_out = (
                    p.slug == "e2e-hoodie-03"
                    or (p.slug == "e2e-hoodie-01" and slug == "white")
                    or (p.slug == "e2e-tee-15" and slug == "black" and code == "l")
                )
                stock = 0 if sold_out else 5
                VariantSize.objects.create(variant=v, size=size, sku=f"{p.slug}-{slug}-{code}", stock_quantity=stock)

    for n in range(1, 16):
        make(n, hoodies, "Hoodie")
        make(n, tees, "Tee")
print("seeded", Product.objects.count(), "products")
