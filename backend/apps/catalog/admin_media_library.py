"""Unified, read-only media index for existing product and homepage-banner assets.

Uploads and destructive operations stay in their owning workflows. This endpoint
only provides a permission-filtered view across the media already in the catalog.
"""
from datetime import datetime

from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import HomepageBanner, VariantImage
from .pagination import CatalogPagination
from .storage import public_image_url


@method_decorator(never_cache, name="dispatch")
class AdminMediaLibraryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user.is_active or not user.is_staff:
            return Response(status=403)

        can_view_products = user.has_perm("catalog.view_variantimage")
        can_view_banners = user.has_perm("catalog.view_homepagebanner")
        if not (can_view_products or can_view_banners):
            return Response(status=403)

        source = request.query_params.get("source", "all")
        if source not in {"all", "product", "banner"}:
            return Response({"error": {"code": "invalid_source"}}, status=400)
        query = request.query_params.get("q", "").strip()[:100]
        if query and len(query) < 2:
            return Response({"error": {"code": "query_too_short"}}, status=400)

        rows = []
        if can_view_products and source in {"all", "product"}:
            images = VariantImage.objects.filter(is_active=True).select_related(
                "variant__product"
            ).order_by("-created_at", "-id")
            if query:
                images = images.filter(
                    Q(alt_text__icontains=query)
                    | Q(variant__name__icontains=query)
                    | Q(variant__product__name__icontains=query)
                    | Q(variant__product__product_code__icontains=query)
                )
            for item in images:
                display_key = item.display_storage_key or item.storage_key
                thumbnail_key = item.thumbnail_storage_key or display_key
                rows.append({
                    "id": f"product-{item.pk}",
                    "source": "product",
                    "source_id": item.pk,
                    "source_label": "تصویر محصول",
                    "title": item.variant.product.name,
                    "alt_text": item.alt_text,
                    "url": public_image_url(display_key),
                    "thumbnail_url": public_image_url(thumbnail_key),
                    "width": item.width,
                    "height": item.height,
                    "file_size": item.file_size,
                    "created_at": item.created_at,
                    "owner_label": f"{item.variant.product.name} · {item.variant.name}",
                    "owner_url": "/admin-panel/catalog",
                })

        if can_view_banners and source in {"all", "banner"}:
            banners = HomepageBanner.objects.exclude(desktop_image="").order_by("-created_at", "-id")
            if query:
                banners = banners.filter(Q(title__icontains=query) | Q(alt_text__icontains=query))
            for banner in banners:
                for field_name, label in (
                    ("desktop_image", "تصویر دسکتاپ بنر"),
                    ("mobile_image", "تصویر موبایل بنر"),
                ):
                    image = getattr(banner, field_name)
                    if not image or not image.name:
                        continue
                    rows.append({
                        "id": f"banner-{banner.pk}-{field_name}",
                        "source": "banner",
                        "source_id": banner.pk,
                        "source_label": label,
                        "title": banner.title or f"بنر شماره {banner.pk}",
                        "alt_text": banner.alt_text,
                        "url": image.url,
                        "thumbnail_url": image.url,
                        "width": None,
                        "height": None,
                        "file_size": None,
                        "created_at": banner.created_at,
                        "owner_label": banner.title or f"بنر شماره {banner.pk}",
                        "owner_url": "/admin-panel/homepage/banners",
                    })

        rows.sort(key=lambda item: (item["created_at"], item["id"]), reverse=True)
        paginator = CatalogPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        for item in page:
            item["created_at"] = item["created_at"].isoformat()
        return paginator.get_paginated_response(page)
