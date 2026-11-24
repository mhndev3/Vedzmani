"""Staff-only API for managing homepage sections and their revision history."""
from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, DjangoModelPermissions
from rest_framework.response import Response

from .models import Category, HomepageSection, HomepageSectionRevision, Product


class HomepageSectionAdminSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(many=True, queryset=Category.objects.filter(is_active=True), required=False)
    products = serializers.PrimaryKeyRelatedField(many=True, queryset=Product.objects.filter(is_active=True, category__is_active=True), required=False)

    class Meta:
        model = HomepageSection
        fields = ["id", "title", "eyebrow", "section_type", "status", "position", "item_limit", "show_view_all", "view_all_url", "categories", "products", "created_at", "updated_at", "published_at"]
        read_only_fields = ["id", "created_at", "updated_at", "published_at"]

    def validate_view_all_url(self, value):
        if value and (not value.startswith("/") or value.startswith("//")):
            raise serializers.ValidationError("Only same-site relative paths are allowed.")
        return value

    def validate_item_limit(self, value):
        if value < 1 or value > 24:
            raise serializers.ValidationError("تعداد نمایش باید بین ۱ تا ۲۴ باشد.")
        return value

    def validate(self, attrs):
        section_type = attrs.get("section_type", getattr(self.instance, "section_type", None))
        categories = attrs.get("categories", list(self.instance.categories.all()) if self.instance else [])
        products = attrs.get("products", list(self.instance.products.all()) if self.instance else [])
        if section_type == HomepageSection.TYPE_CATEGORIES:
            if not categories:
                raise serializers.ValidationError({"categories": "برای بخش دسته‌بندی حداقل یک دسته‌بندی انتخاب کنید."})
            if products:
                raise serializers.ValidationError({"products": "بخش دسته‌بندی نمی‌تواند محصول انتخابی داشته باشد."})
        elif section_type == HomepageSection.TYPE_PRODUCTS:
            if not products:
                raise serializers.ValidationError({"products": "برای این بخش حداقل یک محصول انتخاب کنید."})
            if categories:
                raise serializers.ValidationError({"categories": "بخش محصولات نمی‌تواند دسته‌بندی انتخابی داشته باشد."})
        elif section_type == HomepageSection.TYPE_NEWEST_PRODUCTS:
            if categories:
                raise serializers.ValidationError({"categories": "بخش جدیدترین محصولات نمی‌تواند دسته‌بندی انتخابی داشته باشد."})
            # Explicitly selected products are pinned before the automatically newest cards.
        return attrs

    def update(self, instance, validated_data):
        if validated_data.get("status", instance.status) == HomepageSection.STATUS_PUBLISHED and instance.status != HomepageSection.STATUS_PUBLISHED:
            validated_data["published_at"] = timezone.now()
        return super().update(instance, validated_data)

    def create(self, validated_data):
        if validated_data.get("status") == HomepageSection.STATUS_PUBLISHED:
            validated_data["published_at"] = timezone.now()
        return super().create(validated_data)


class HomepageSectionRevisionSerializer(serializers.ModelSerializer):
    created_by_label = serializers.SerializerMethodField()

    class Meta:
        model = HomepageSectionRevision
        fields = ["id", "action", "snapshot", "created_by_label", "created_at"]
        read_only_fields = fields

    def get_created_by_label(self, obj):
        if obj.created_by is None:
            return "سیستم"
        return obj.created_by.phone or obj.created_by.get_username()


def section_snapshot(section):
    return {
        "title": section.title,
        "eyebrow": section.eyebrow,
        "section_type": section.section_type,
        "status": section.status,
        "position": section.position,
        "item_limit": section.item_limit,
        "show_view_all": section.show_view_all,
        "view_all_url": section.view_all_url,
        "categories": list(section.categories.order_by("id").values_list("id", flat=True)),
        "products": list(section.products.order_by("id").values_list("id", flat=True)),
    }


def record_section_revision(section, actor, action):
    return HomepageSectionRevision.objects.create(
        section=section,
        snapshot=section_snapshot(section),
        action=action,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


class StaffHomepagePermissions(DjangoModelPermissions):
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


class HomepageSectionRevisionPermissions(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_staff:
            return False
        permission = "catalog.view_homepagesection" if request.method == "GET" else ("catalog.delete_homepagesection" if request.method == "DELETE" else "catalog.change_homepagesection")
        return request.method in {"GET", "POST", "DELETE"} and user.has_perm(permission)


class HomepageSectionAdminViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Create/read/update/delete homepage sections behind explicit model permissions."""

    serializer_class = HomepageSectionAdminSerializer
    permission_classes = [StaffHomepagePermissions]
    queryset = HomepageSection.objects.prefetch_related("categories", "products").all()
    pagination_class = None

    def get_permissions(self):
        if getattr(self, "action", None) == "revisions":
            return [HomepageSectionRevisionPermissions()]
        return super().get_permissions()

    @transaction.atomic
    def perform_create(self, serializer):
        section = serializer.save()
        record_section_revision(section, self.request.user, HomepageSectionRevision.ACTION_CREATED)

    @transaction.atomic
    def perform_update(self, serializer):
        section = serializer.save()
        record_section_revision(section, self.request.user, HomepageSectionRevision.ACTION_UPDATED)

    @transaction.atomic
    @action(detail=True, methods=["get", "post"], url_path="revisions")
    def revisions(self, request, pk=None):
        section = self.get_object()
        if request.method == "GET":
            revisions = section.revisions.select_related("created_by").all()
            return Response(HomepageSectionRevisionSerializer(revisions, many=True).data)

        revision_id = request.data.get("revision_id")
        if not str(revision_id or "").isdigit():
            raise ValidationError({"revision_id": "شناسه نسخه معتبر نیست."})
        revision = section.revisions.filter(pk=int(revision_id)).first()
        if revision is None:
            raise ValidationError({"revision_id": "این نسخه متعلق به بخش انتخاب‌شده نیست."})

        serializer = self.get_serializer(section, data=revision.snapshot)
        serializer.is_valid(raise_exception=True)
        restored = serializer.save()
        record_section_revision(restored, request.user, HomepageSectionRevision.ACTION_ROLLBACK)
        return Response(self.get_serializer(restored).data, status=status.HTTP_200_OK)
