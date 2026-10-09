from django.db.models import Exists, Min, OuterRef, Prefetch
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Category, Collection, ColorVariant, Product, Size, VariantImage, VariantSize
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


class FilterOptionsView(APIView):
    """Public filter vocabulary for the storefront: only values that exist on published products.

    Fixed cost: 4 queries (categories, collections, colors, sizes), no per-product work.
    """

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        live = Product.objects.filter(is_active=True, category__is_active=True)
        live_variants = ColorVariant.objects.filter(
            is_active=True, product__is_active=True, product__category__is_active=True
        )
        categories = (
            Category.objects.filter(is_active=True)
            .filter(Exists(live.filter(category=OuterRef("pk"))))
            .order_by("position", "name", "id")
            .values("name", "slug")
        )
        collections = (
            Collection.objects.filter(is_active=True)
            .filter(
                Exists(
                    Product.collections.through.objects.filter(
                        collection_id=OuterRef("pk"),
                        product__is_active=True,
                        product__category__is_active=True,
                    )
                )
            )
            .order_by("position", "name", "id")
            .values("name", "slug")
        )
        colors = (
            live_variants.order_by()
            .values("slug")
            .annotate(name=Min("name"), hex_color=Min("hex_color"))
            .order_by("name", "slug")
            .values("name", "slug", "hex_color")
        )
        sizes = (
            Size.objects.filter(
                Exists(
                    VariantSize.objects.filter(
                        size=OuterRef("pk"),
                        is_active=True,
                        variant__is_active=True,
                        variant__product__is_active=True,
                        variant__product__category__is_active=True,
                    )
                )
            )
            .order_by("position", "code")
            .values("code", "label")
        )
        return Response(
            {
                "categories": list(categories),
                "collections": list(collections),
                "colors": list(colors),
                "sizes": list(sizes),
            }
        )
