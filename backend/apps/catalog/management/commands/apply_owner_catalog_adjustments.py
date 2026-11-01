from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.catalog.models import Product, VariantImage, VariantSize
from apps.inventory.models import InventoryAdjustment
from apps.inventory.services import adjust_stock


OWNER_STOCK_REASON = "افزایش یک واحد موجودی طبق درخواست مالک: وست جین / آبی روشن / XXL"

IMAGE_PAIRS = (
    (
        "products/dors-two-tone-green-white/green-white/01.054b05e7af52.w1600.webp",
        "products/dors-two-tone-green-white/green-white/04.6cf2b0656227.w1600.webp",
    ),
    (
        "products/dors-two-tone-grey-black/grey-black/01.ee1530f7ac6f.w1600.webp",
        "products/dors-two-tone-grey-black/grey-black/04.b3fbbcebf49c.w1600.webp",
    ),
    (
        "products/dors-two-tone-black-red/black-red/01.37970861bb56.w1600.webp",
        "products/dors-two-tone-black-red/black-red/04.9f9053bd0416.w1600.webp",
    ),
)


class Command(BaseCommand):
    help = "Preview/apply the owner-requested catalog image swaps and one West Jeans stock increment."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Persist changes. Without this flag, only preview.")

    def _image(self, key):
        rows = list(VariantImage.objects.select_related("variant__product").filter(display_storage_key=key))
        if len(rows) != 1:
            raise CommandError(f"Expected exactly one image row for {key!r}; found {len(rows)}. No changes applied.")
        return rows[0]

    def _stock_row(self):
        products = list(Product.objects.filter(name__iexact="وست جین", is_active=True))
        if len(products) != 1:
            raise CommandError(f"Expected exactly one active product named «وست جین»; found {len(products)}.")
        rows = list(
            VariantSize.objects.select_related("variant__product", "variant", "size").filter(
                variant__product=products[0],
                variant__is_active=True,
                is_active=True,
                variant__name__iexact="آبی روشن",
            ).filter(Q(size__code__iexact="xxl") | Q(size__label__iexact="XXL"))
        )
        if len(rows) != 1:
            raise CommandError(f"Expected exactly one active XXL size for the «آبی روشن» variant; found {len(rows)}.")
        return rows[0]

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        images = []
        for left_key, right_key in IMAGE_PAIRS:
            left, right = self._image(left_key), self._image(right_key)
            if left.variant_id != right.variant_id:
                raise CommandError(f"Image pair is not in the same color variant: {left_key!r} / {right_key!r}.")
            if left.pk == right.pk:
                raise CommandError("The two image keys resolved to the same database row.")
            images.append((left, right))
            self.stdout.write(
                f"IMAGE_SWAP product={left.variant.product.product_code or left.variant.product.name} "
                f"variant={left.variant.slug} positions={left.position}<->{right.position} "
                f"primary={left.is_primary}<->{right.is_primary}"
            )

        stock_row = self._stock_row()
        if InventoryAdjustment.objects.filter(variant_size=stock_row, reason=OWNER_STOCK_REASON).exists():
            if apply_changes:
                raise CommandError("Owner catalog adjustment was already applied; refusing to swap images back or add stock twice.")
            self.stdout.write(self.style.WARNING("ALREADY_APPLIED: no changes are necessary."))
            return

        self.stdout.write(
            f"STOCK product={stock_row.variant.product.name!r} variant={stock_row.variant.name!r} "
            f"size={stock_row.size.label!r} current={stock_row.stock_quantity} change=+1 after={stock_row.stock_quantity + 1}"
        )

        if not apply_changes:
            self.stdout.write(self.style.WARNING("DRY_RUN_ONLY: no database changes were made. Re-run with --apply after reviewing the matches."))
            return

        with transaction.atomic():
            for left, right in images:
                left_position, left_primary = left.position, left.is_primary
                right_position, right_primary = right.position, right.is_primary
                temp_position = max(left_position, right_position) + 1
                VariantImage.objects.filter(pk=left.pk).update(position=temp_position, is_primary=False)
                VariantImage.objects.filter(pk=right.pk).update(position=left_position, is_primary=left_primary)
                VariantImage.objects.filter(pk=left.pk).update(position=right_position, is_primary=right_primary)

            adjust_stock(
                variant_size_id=stock_row.pk,
                quantity_change=1,
                reason=OWNER_STOCK_REASON,
            )

        self.stdout.write(self.style.SUCCESS("OWNER_CATALOG_ADJUSTMENTS_APPLIED"))
