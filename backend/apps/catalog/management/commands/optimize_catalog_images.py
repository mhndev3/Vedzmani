from django.core.management.base import BaseCommand, CommandError

from apps.catalog.image_processing import OPTIMIZATION_VERSION, optimize_variant_image
from apps.catalog.models import VariantImage


class Command(BaseCommand):
    help = (
        "Generate cache-safe 640px and 1600px WebP renditions for catalog images. "
        "Original files are never modified."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report pending rows and missing files without writing derivatives or database fields.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Regenerate renditions even when the current optimization version is present.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        queryset = VariantImage.objects.order_by("pk")
        if not force:
            queryset = queryset.filter(optimization_version__lt=OPTIMIZATION_VERSION)

        processed = missing = failed = 0
        total = queryset.count()
        if dry_run:
            self.stdout.write(f"Dry run: {total} image row(s) need optimization.")
            return

        for image in queryset.iterator(chunk_size=50):
            try:
                if optimize_variant_image(image.pk, force=force):
                    processed += 1
                else:
                    missing += 1
            except Exception as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(f"Image #{image.pk} failed: {exc}"))

        self.stdout.write(
            f"Processed: {processed}; missing source files: {missing}; failed: {failed}; examined: {total}."
        )
        if failed:
            raise CommandError(f"{failed} catalog image(s) could not be optimized.")
