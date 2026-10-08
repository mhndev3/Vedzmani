from django.db.models import Prefetch
from rest_framework.generics import ListAPIView, RetrieveAPIView

from .models import ColorVariant, Product, VariantImage, VariantSize
from .filters import CatalogQuerySerializer, active_colors_queryset, build_product_queryset
from .pagination import CatalogPagination
from .serializers import ProductDetailSerializer, ProductListSerializer


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

class ProductListView(ListAPIView):
    """Public, paginated listing of active products with search, filters and whitelisted sorting.

    All filtering/sorting is in SQL; per page: 1 count + 1 products + 1 color swatches query.
    """

    serializer_class = ProductListSerializer
    pagination_class = CatalogPagination
    authentication_classes: list = []
    permission_classes: list = []

    def get_queryset(self):
        params = CatalogQuerySerializer(data=self.request.query_params, partial=True)
        params.is_valid(raise_exception=True)
        return build_product_queryset(params.validated_data).prefetch_related(
            Prefetch("color_variants", queryset=active_colors_queryset(), to_attr="active_colors")
        )
