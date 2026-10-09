"""E2E-only fixture data for the catalog tests (NOT production data).

Run against a throwaway database, never the real one:
  cd backend; DATABASE_URL=postgres://.../vedzmani_e2e python manage.py shell < ../e2e/seed_catalog.py
Idempotent: skips if the fixture products already exist.
"""

from decimal import Decimal

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
                stock = 0 if (p.slug == "e2e-hoodie-03" or (p.slug == "e2e-hoodie-01" and slug == "white")) else 5
                VariantSize.objects.create(variant=v, size=size, sku=f"{p.slug}-{slug}-{code}", stock_quantity=stock)

    for n in range(1, 16):
        make(n, hoodies, "Hoodie")
        make(n, tees, "Tee")
print("seeded", Product.objects.count(), "products")
