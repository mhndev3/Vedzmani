"""Public read-only homepage sections. Only published configuration and active catalog data leave the API."""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import build_variant_queryset
from .models import HomepageSection
from .serializers import VariantProductListSerializer
from .storage import public_image_url


class HomepageSectionsPublicView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        sections = HomepageSection.objects.filter(status=HomepageSection.STATUS_PUBLISHED).prefetch_related(
            "categories", "products"
        )
        result = []
        for section in sections:
            row = {
                "id": section.pk,
                "title": section.title,
                "eyebrow": section.eyebrow,
                "section_type": section.section_type,
                "show_view_all": section.show_view_all,
                "view_all_url": section.view_all_url,
                "categories": [],
                "category_ids": list(section.categories.order_by("position", "id").values_list("id", flat=True)),
                "products": [],
                "product_ids": list(section.products.order_by("id").values_list("id", flat=True)),
            }
            if section.section_type == HomepageSection.TYPE_CATEGORIES:
                categories = section.categories.filter(is_active=True).order_by("position", "id")[:section.item_limit]
                for category in categories:
                    variants = build_variant_queryset({}).filter(product__category=category)
                    product = VariantProductListSerializer(variants[:1], many=True, context={"request": request}).data
                    category_image = None
                    if category.image:
                        category_image = {
                            "url": public_image_url(category.image.name),
                            "thumbnail_url": public_image_url(category.image.name),
                            "alt_text": category.name,
                        }
                    row["categories"].append({
                        "id": category.pk,
                        "name": category.name,
                        "slug": category.slug,
                        "image": category_image or (product[0]["image"] if product else None),
                    })
            elif section.section_type == HomepageSection.TYPE_PRODUCTS:
                product_ids = section.products.filter(is_active=True, category__is_active=True).values_list("id", flat=True)
                variants = build_variant_queryset({}).filter(product_id__in=product_ids)[:section.item_limit]
                row["products"] = VariantProductListSerializer(variants, many=True, context={"request": request}).data
            else:
                pinned_ids = list(section.products.filter(
                    is_active=True, category__is_active=True
                ).order_by("id").values_list("id", flat=True))
                pinned_variants = list(
                    build_variant_queryset({}).filter(product_id__in=pinned_ids)[:section.item_limit]
                )
                remaining = section.item_limit - len(pinned_variants)
                if remaining > 0:
                    newest_variants = list(
                        build_variant_queryset({}).exclude(product_id__in=pinned_ids)[:remaining]
                    )
                else:
                    newest_variants = []
                variants = pinned_variants + newest_variants
                row["products"] = VariantProductListSerializer(
                    variants, many=True, context={"request": request}
                ).data
            result.append(row)
        return Response({"sections": result})
