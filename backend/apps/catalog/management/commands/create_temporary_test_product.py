from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Category, ColorVariant, Product, Size, VariantSize
from apps.inventory.services import adjust_stock


CATEGORY_SLUG = "temporary-test-products"
PRODUCT_SLUG = "vedzmani-test-product"
SIZE_CODE = "free"
VARIANT_SLUG = "white"
SKU = "TEST-FREE-001"
STOCK_REASON = "موجودی اولیه محصول تست موقت"


class Command(BaseCommand):
    help = "Create the temporary 1,000 toman storefront test product. Dry-run unless --apply is passed."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist changes; otherwise only preview.")

    def handle(self, *args, **options):
        existing = Product.objects.filter(slug=PRODUCT_SLUG).first()
        if existing:
            variant_size = VariantSize.objects.filter(
                variant__product=existing, variant__slug=VARIANT_SLUG, size__code=SIZE_CODE
            ).select_related("variant", "size").first()
            if (
                existing.name != "تست" or existing.price != 1000 or not existing.is_active
                or variant_size is None or variant_size.sku != SKU
            ):
                raise CommandError("Reserved test slug exists with unexpected data. No changes were made.")
            self.stdout.write(self.style.WARNING(
                f"ALREADY_EXISTS: product_id={existing.pk}, stock={variant_size.stock_quantity}. "
                "No stock will be added again."
            ))
            return

        self.stdout.write(
            "PLAN: active product «تست», price=1000 toman, category=محصولات آزمایشی, "
            "variant=سفید, size=فری سایز, initial stock=1."
        )
        if not options["apply"]:
            self.stdout.write(self.style.WARNING("DRY_RUN_ONLY: no database changes. Re-run with --apply."))
            return

        with transaction.atomic():
            category, _ = Category.objects.get_or_create(
                slug=CATEGORY_SLUG,
                defaults={"name": "محصولات آزمایشی", "position": 99, "is_active": True},
            )
            size, _ = Size.objects.get_or_create(
                code=SIZE_CODE, defaults={"label": "فری سایز", "position": 99}
            )
            category.sizes.add(size)
            product = Product.objects.create(
                category=category, product_code=None, name="تست", slug=PRODUCT_SLUG,
                description="محصول آزمایشی موقت برای بررسی فرایند خرید.",
                price=1000, is_active=True,
            )
            variant = ColorVariant.objects.create(
                product=product, name="سفید", slug=VARIANT_SLUG, hex_color="#FFFFFF",
                is_active=True, position=0,
            )
            variant_size = VariantSize.objects.create(
                variant=variant, size=size, sku=SKU, stock_quantity=0, is_active=True,
            )
            adjustment = adjust_stock(
                variant_size_id=variant_size.pk, quantity_change=1, reason=STOCK_REASON,
            )

        self.stdout.write(self.style.SUCCESS(
            f"TEMPORARY_TEST_PRODUCT_CREATED: product_id={product.pk}, "
            f"variant_size_id={variant_size.pk}, stock={adjustment.stock_after}, price=1000 toman."
        ))
