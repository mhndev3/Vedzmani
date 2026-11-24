"""Staff-only homepage banner management API."""
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from PIL import Image, UnidentifiedImageError
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, DjangoModelPermissions
from rest_framework.response import Response

from .models import HomepageBanner, HomepageBannerGroup, HomepageBannerRevision, VariantImage


def banner_snapshot(banner):
    return {
        "title": banner.title,
        "subtitle": banner.subtitle,
        "alt_text": banner.alt_text,
        "desktop_image": banner.desktop_image.name,
        "mobile_image": banner.mobile_image.name if banner.mobile_image else "",
        "cta_label": banner.cta_label,
        "cta_url": banner.cta_url,
        "position": banner.position,
        "status": banner.status,
        "starts_at": banner.starts_at.isoformat() if banner.starts_at else None,
        "ends_at": banner.ends_at.isoformat() if banner.ends_at else None,
    }


def record_banner_revision(banner, actor, action):
    return HomepageBannerRevision.objects.create(
        banner=banner,
        snapshot=banner_snapshot(banner),
        action=action,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


class HomepageBannerRevisionSerializer(serializers.ModelSerializer):
    snapshot = serializers.SerializerMethodField()
    created_by_label = serializers.SerializerMethodField()

    class Meta:
        model = HomepageBannerRevision
        fields = ["id", "action", "snapshot", "created_by_label", "created_at"]
        read_only_fields = fields

    def get_created_by_label(self, obj):
        if obj.created_by is None:
            return "سیستم"
        return obj.created_by.phone or obj.created_by.get_username()

    def get_snapshot(self, obj):
        snapshot = dict(obj.snapshot)
        snapshot["desktop_image"] = bool(snapshot.get("desktop_image"))
        snapshot["mobile_image"] = bool(snapshot.get("mobile_image"))
        return snapshot


class HomepageBannerRevisionPermissions(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_staff:
            return False
        permission = "catalog.view_homepagebanner" if request.method == "GET" else "catalog.change_homepagebanner"
        return request.method in {"GET", "POST"} and user.has_perm(permission)


def resolve_media_library_reference(reference, user):
    """Resolve a public library item ID to an existing storage key without exposing keys to clients."""
    parts = str(reference or "").split("-")
    if len(parts) == 2 and parts[0] == "product" and parts[1].isdigit():
        if not user.has_perm("catalog.view_variantimage"):
            raise serializers.ValidationError("مجوز استفاده از تصاویر محصولات را ندارید.")
        image = VariantImage.objects.filter(pk=int(parts[1]), is_active=True).first()
        if image is None:
            raise serializers.ValidationError("تصویر محصول در کتابخانه موجود یا فعال نیست.")
        key = image.display_storage_key or image.storage_key
    elif len(parts) == 3 and parts[0] == "banner" and parts[1].isdigit() and parts[2] in {"desktop_image", "mobile_image"}:
        if not user.has_perm("catalog.view_homepagebanner"):
            raise serializers.ValidationError("مجوز استفاده از تصاویر بنرها را ندارید.")
        banner = HomepageBanner.objects.filter(pk=int(parts[1])).first()
        if banner is None:
            raise serializers.ValidationError("بنر انتخاب‌شده پیدا نشد.")
        image = getattr(banner, parts[2])
        key = image.name if image else ""
        if not key:
            raise serializers.ValidationError("تصویر انتخاب‌شده دیگر در دسترس نیست.")
    else:
        raise serializers.ValidationError("شناسه رسانه معتبر نیست.")
    if not default_storage.exists(key):
        raise serializers.ValidationError("فایل تصویر انتخاب‌شده در فضای ذخیره‌سازی موجود نیست.")
    return key


class HomepageBannerAdminSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=HomepageBannerGroup.objects.filter(is_active=True), required=False)
    desktop_image_url = serializers.SerializerMethodField()
    mobile_image_url = serializers.SerializerMethodField()
    desktop_image_media_ref = serializers.CharField(write_only=True, required=False, allow_blank=False)
    mobile_image_media_ref = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = HomepageBanner
        fields = [
            "id", "group", "title", "subtitle", "alt_text", "desktop_image", "mobile_image",
            "desktop_image_url", "mobile_image_url", "desktop_image_media_ref", "mobile_image_media_ref", "cta_label", "cta_url",
            "position", "status", "starts_at", "ends_at", "created_at",
            "updated_at", "published_at",
        ]
        read_only_fields = [
            "id", "desktop_image_url", "mobile_image_url", "created_at",
            "updated_at", "published_at",
        ]
        extra_kwargs = {
            "desktop_image": {"required": False},
            "mobile_image": {"required": False},
        }

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
        if self.instance is None and "group" not in attrs:
            default_group = HomepageBannerGroup.objects.filter(slug="main", is_active=True).first()
            if default_group is None:
                raise serializers.ValidationError({"group": "ابتدا یک گروه فعال برای بنرها بسازید."})
            attrs["group"] = default_group
        for field in ("desktop_image", "mobile_image"):
            reference_field = f"{field}_media_ref"
            if attrs.get(field) and attrs.get(reference_field):
                raise serializers.ValidationError({reference_field: "هم‌زمان فایل جدید و تصویر کتابخانه را انتخاب نکنید."})
            if attrs.get(reference_field):
                attrs[f"_{field}_storage_key"] = resolve_media_library_reference(
                    attrs[reference_field], self.context["request"].user
                )
        uploaded_size = sum(
            getattr(attrs.get(field), "size", 0)
            for field in ("desktop_image", "mobile_image")
        )
        if uploaded_size > 7 * 1024 * 1024:
            raise serializers.ValidationError("حجم مجموع تصاویر ارسالی در هر درخواست نباید بیشتر از ۷ مگابایت باشد.")
        if self.instance is None and not attrs.get("desktop_image") and not attrs.get("_desktop_image_storage_key"):
            raise serializers.ValidationError({"desktop_image": "برای بنر جدید، تصویر دسکتاپ الزامی است."})
        starts_at = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends_at = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts_at and ends_at and ends_at <= starts_at:
            raise serializers.ValidationError({"ends_at": "زمان پایان باید بعد از زمان شروع باشد."})
        if attrs.get("status", getattr(self.instance, "status", HomepageBanner.STATUS_DRAFT)) == HomepageBanner.STATUS_PUBLISHED:
            alt_text = attrs.get("alt_text", getattr(self.instance, "alt_text", ""))
            desktop_image = attrs.get("desktop_image") or attrs.get("_desktop_image_storage_key") or getattr(self.instance, "desktop_image", None)
            if not alt_text.strip() or not desktop_image:
                raise serializers.ValidationError("برای انتشار، تصویر دسکتاپ و متن جایگزین الزامی است.")
        return attrs

    def _apply_library_images(self, banner, storage_keys):
        changed = []
        for field, key in storage_keys.items():
            if key:
                getattr(banner, field).name = key
                changed.append(field)
        if changed:
            banner.save(update_fields=changed + ["updated_at"])
        return banner

    def create(self, validated_data):
        storage_keys = {
            field: validated_data.pop(f"_{field}_storage_key", "")
            for field in ("desktop_image", "mobile_image")
        }
        validated_data.pop("desktop_image_media_ref", None)
        validated_data.pop("mobile_image_media_ref", None)
        if validated_data.get("status") == HomepageBanner.STATUS_PUBLISHED:
            validated_data["published_at"] = timezone.now()
        banner = super().create(validated_data)
        return self._apply_library_images(banner, storage_keys)

    def update(self, instance, validated_data):
        storage_keys = {
            field: validated_data.pop(f"_{field}_storage_key", "")
            for field in ("desktop_image", "mobile_image")
        }
        validated_data.pop("desktop_image_media_ref", None)
        validated_data.pop("mobile_image_media_ref", None)
        if validated_data.get("status", instance.status) == HomepageBanner.STATUS_PUBLISHED and instance.status != HomepageBanner.STATUS_PUBLISHED:
            validated_data["published_at"] = timezone.now()
        banner = super().update(instance, validated_data)
        return self._apply_library_images(banner, storage_keys)


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

    def get_permissions(self):
        if getattr(self, "action", None) == "revisions":
            return [HomepageBannerRevisionPermissions()]
        return super().get_permissions()

    @transaction.atomic
    def perform_create(self, serializer):
        banner = serializer.save()
        record_banner_revision(banner, self.request.user, HomepageBannerRevision.ACTION_CREATED)

    @transaction.atomic
    def perform_update(self, serializer):
        banner = serializer.save()
        record_banner_revision(banner, self.request.user, HomepageBannerRevision.ACTION_UPDATED)

    @transaction.atomic
    @action(detail=True, methods=["get", "post"], url_path="revisions")
    def revisions(self, request, pk=None):
        banner = self.get_object()
        if request.method == "GET":
            rows = banner.revisions.select_related("created_by").all()
            return Response(HomepageBannerRevisionSerializer(rows, many=True).data)

        revision_id = request.data.get("revision_id")
        if not str(revision_id or "").isdigit():
            raise ValidationError({"revision_id": "شناسه نسخه معتبر نیست."})
        revision = banner.revisions.filter(pk=int(revision_id)).first()
        if revision is None:
            raise ValidationError({"revision_id": "این نسخه متعلق به بنر انتخاب‌شده نیست."})
        snapshot = revision.snapshot
        desktop_key = snapshot.get("desktop_image") or ""
        mobile_key = snapshot.get("mobile_image") or ""
        if not desktop_key or not HomepageBanner._meta.get_field("desktop_image").storage.exists(desktop_key):
            raise ValidationError({"revision_id": "تصویر دسکتاپ این نسخه دیگر در فضای ذخیره‌سازی موجود نیست."})
        if mobile_key and not HomepageBanner._meta.get_field("mobile_image").storage.exists(mobile_key):
            raise ValidationError({"revision_id": "تصویر موبایل این نسخه دیگر در فضای ذخیره‌سازی موجود نیست."})

        values = {key: value for key, value in snapshot.items() if key not in {"desktop_image", "mobile_image"}}
        serializer = self.get_serializer(banner, data=values, partial=True)
        serializer.is_valid(raise_exception=True)
        restored = serializer.save()
        restored.desktop_image.name = desktop_key
        restored.mobile_image.name = mobile_key
        restored.save(update_fields=["desktop_image", "mobile_image", "updated_at"])
        record_banner_revision(restored, request.user, HomepageBannerRevision.ACTION_ROLLBACK)
        return Response(self.get_serializer(restored).data, status=status.HTTP_200_OK)
