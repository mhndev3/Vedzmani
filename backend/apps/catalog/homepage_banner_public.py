"""Public homepage banner groups. Only active groups and published, in-window banners are exposed."""
from django.db import models
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import HomepageBanner, HomepageBannerGroup


def banner_payload(banner):
    return {
        "id": banner.pk,
        "title": banner.title,
        "subtitle": banner.subtitle,
        "alt_text": banner.alt_text,
        "desktop_image": banner.desktop_image.url,
        "mobile_image": banner.mobile_image.url if banner.mobile_image else None,
        "cta_label": banner.cta_label,
        "cta_url": banner.cta_url,
    }


class HomepageBannersPublicView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        now = timezone.now()
        active_banners = HomepageBanner.objects.filter(
            status=HomepageBanner.STATUS_PUBLISHED,
        ).filter(
            models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now),
            models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now),
        ).order_by("position", "id")

        groups = HomepageBannerGroup.objects.filter(is_active=True).prefetch_related(
            Prefetch("banners", queryset=active_banners)
        )
        grouped = []
        flattened = []
        for group in groups:
            banners = [banner_payload(banner) for banner in group.banners.all()]
            if not banners:
                continue
            grouped.append({
                "id": group.pk,
                "name": group.name,
                "slug": group.slug,
                "position": group.position,
                "banners": banners,
            })
            flattened.extend(banners)

        return Response({"groups": grouped, "banners": flattened})
