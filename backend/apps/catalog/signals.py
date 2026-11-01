from django.db.models.signals import post_save
from django.dispatch import receiver

from .image_processing import schedule_variant_image_optimization
from .models import VariantImage


@receiver(post_save, sender=VariantImage, dispatch_uid="catalog.optimize_variant_image")
def optimize_saved_variant_image(sender, instance: VariantImage, raw: bool, **kwargs) -> None:
    if raw:
        return
    schedule_variant_image_optimization(instance)
