"""Public read-only homepage sections. Only published configuration and active catalog data leave the API."""
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .filters import build_variant_queryset
from .models import HomepageSection
from .serializers import VariantProductListSerializer


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
                "products": [],
            }
            if section.section_type == HomepageSection.TYPE_CATEGORIES:
                categories = section.categories.filter(is_active=True).order_by("position", "id")[:section.item_limit]
                for category in categories:
                    variants = build_variant_queryset({}).filter(product__category=category)
                    product = VariantProductListSerializer(variants[:1], many=True, context={"request": request}).data
                    row["categories"].append({
                        "name": category.name,
                        "slug": category.slug,
                        "image": product[0]["image"] if product else None,
                    })
            elif section.section_type == HomepageSection.TYPE_PRODUCTS:
                product_ids = section.products.filter(is_active=True, category__is_active=True).values_list("id", flat=True)
                variants = build_variant_queryset({}).filter(product_id__in=product_ids)[:section.item_limit]
                row["products"] = VariantProductListSerializer(variants, many=True, context={"request": request}).data
            else:
                variants = build_variant_queryset({})[:section.item_limit]
                row["products"] = VariantProductListSerializer(variants, many=True, context={"request": request}).data
            result.append(row)
        return Response({"sections": result})
