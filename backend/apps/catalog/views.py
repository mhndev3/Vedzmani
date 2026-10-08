from django.db.models import Prefetch
from rest_framework.generics import RetrieveAPIView

from .models import ColorVariant, Product, VariantImage, VariantSize
from .serializers import ProductDetailSerializer


class ProductDetailView(RetrieveAPIView):
    """Public read of one active product with active colors, images and sizes.

    Fixed query count regardless of variant count (select_related + prefetch).
    """

    serializer_class = ProductDetailSerializer
    lookup_field = "slug"
    authentication_classes: list = []
    permission_classes: list = []

    def get_queryset(self):
        variants = ColorVariant.objects.filter(is_active=True).prefetch_related(
            Prefetch("images", queryset=VariantImage.objects.filter(is_active=True)),
            Prefetch("sizes", queryset=VariantSize.objects.filter(is_active=True).select_related("size")),
        )
        return (
            Product.objects.filter(is_active=True, category__is_active=True)
            .select_related("category")
            .prefetch_related(Prefetch("color_variants", queryset=variants))
        )
