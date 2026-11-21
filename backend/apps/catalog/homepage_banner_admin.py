"""Staff-only homepage banner management API."""
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from rest_framework import mixins, serializers, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import DjangoModelPermissions

from .models import HomepageBanner


class HomepageBannerAdminSerializer(serializers.ModelSerializer):
    desktop_image_url = serializers.SerializerMethodField()
    mobile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = HomepageBanner
        fields = [
            "id", "title", "subtitle", "alt_text", "desktop_image", "mobile_image",
            "desktop_image_url", "mobile_image_url", "cta_label", "cta_url",
            "position", "status", "starts_at", "ends_at", "created_at",
            "updated_at", "published_at",
        ]
        read_only_fields = [
            "id", "desktop_image_url", "mobile_image_url", "created_at",
            "updated_at", "published_at",
        ]

    def get_desktop_image_url(self, obj):
        return obj.desktop_image.url if obj.desktop_image else None

    def get_mobile_image_url(self, obj):
        return obj.mobile_image.url if obj.mobile_image else None

    def _validate_image(self, value, field):
        if not value:
            return value
        if value.size <= 0 or value.size > 8 * 1024 * 1024:
            raise serializers.ValidationError("حجم هر تصویر باید بیشتر از صفر و حداکثر ۸ مگابایت باشد.")
        try:
            value.seek(0)
            with Image.open(value) as image:
                if image.format not in {"JPEG", "PNG", "WEBP"}:
                    raise serializers.ValidationError("فرمت تصویر باید JPEG، PNG یا WebP باشد.")
                if image.width < 1 or image.height < 1 or image.width * image.height > 40_000_000:
                    raise serializers.ValidationError("ابعاد تصویر بیش از حد مجاز است.")
                image.verify()
            value.seek(0)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise serializers.ValidationError("فایل تصویر معتبر یا قابل خواندن نیست.") from exc
        return value

    def validate_desktop_image(self, value):
        return self._validate_image(value, "desktop_image")

    def validate_mobile_image(self, value):
        return self._validate_image(value, "mobile_image")

    def validate_cta_url(self, value):
        if value and (not value.startswith("/") or value.startswith("//") or "\\" in value):
            raise serializers.ValidationError("لینک باید یک مسیر داخلی معتبر سایت باشد.")
        return value

    def validate(self, attrs):
        uploaded_size = sum(
            getattr(attrs.get(field), "size", 0)
            for field in ("desktop_image", "mobile_image")
        )
        if uploaded_size > 7 * 1024 * 1024:
            raise serializers.ValidationError("حجم مجموع تصاویر ارسالی در هر درخواست نباید بیشتر از ۷ مگابایت باشد.")
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "زمان پایان باید بعد از زمان شروع باشد."})
        if attrs.get("status", getattr(self.instance, "status", HomepageBanner.STATUS_DRAFT)) == HomepageBanner.STATUS_PUBLISHED:
            alt_text = attrs.get("alt_text", getattr(self.instance, "alt_text", ""))
            desktop_image = attrs.get("desktop_image", getattr(self.instance, "desktop_image", None))
            if not alt_text.strip() or not desktop_image:
                raise serializers.ValidationError("برای انتشار، تصویر دسکتاپ و متن جایگزین الزامی است.")
        return attrs

    def create(self, validated_data):
        if validated_data.get("status") == HomepageBanner.STATUS_PUBLISHED:
            validated_data["published_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if validated_data.get("status", instance.status) == HomepageBanner.STATUS_PUBLISHED and instance.status != HomepageBanner.STATUS_PUBLISHED:
            validated_data["published_at"] = timezone.now()
        return super().update(instance, validated_data)


class StaffHomepageBannerPermissions(DjangoModelPermissions):
    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff and super().has_permission(request, view))


class HomepageBannerAdminViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """No physical delete endpoint; drafts and unpublishing are reversible."""
    queryset = HomepageBanner.objects.all()
    serializer_class = HomepageBannerAdminSerializer
    permission_classes = [StaffHomepageBannerPermissions]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = None
