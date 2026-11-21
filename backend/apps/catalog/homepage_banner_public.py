"""Public homepage banners. Draft and out-of-window content is never exposed."""
from django.db import models\nfrom django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import HomepageBanner


class HomepageBannersPublicView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        now = timezone.now()
        banners = HomepageBanner.objects.filter(
            status=HomepageBanner.STATUS_PUBLISHED,
        ).filter(
            models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now),
            models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now),
        ).order_by("position", "id")
        return Response({
            "banners": [
                {
                    "id": banner.pk,
                    "title": banner.title,
                    "subtitle": banner.subtitle,
                    "alt_text": banner.alt_text,
                    "desktop_image": banner.desktop_image.url,
                    "mobile_image": banner.mobile_image.url if banner.mobile_image else None,
                    "cta_label": banner.cta_label,
                    "cta_url": banner.cta_url,
                }
                for banner in banners
            ]
        })
