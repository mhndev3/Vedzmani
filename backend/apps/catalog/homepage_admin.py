"""Staff-only API for managing homepage sections and their selected catalog items."""
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.permissions import DjangoModelPermissions

from .models import Category, HomepageSection, Product


class HomepageSectionAdminSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(many=True, queryset=Category.objects.filter(is_active=True), required=False)
    products = serializers.PrimaryKeyRelatedField(many=True, queryset=Product.objects.filter(is_active=True, category__is_active=True), required=False)

    class Meta:
        model = HomepageSection
        fields = ["id", "title", "eyebrow", "section_type", "status", "position", "item_limit", "show_view_all", "view_all_url", "categories", "products", "created_at", "updated_at", "published_at"]
        read_only_fields = ["id", "created_at", "updated_at", "published_at"]

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
            if categories or products:
                raise serializers.ValidationError("بخش جدیدترین محصولات انتخاب دستی نمی‌پذیرد.")
        return attrs

    def update(self, instance, validated_data):
        if validated_data.get("status", instance.status) == HomepageSection.STATUS_PUBLISHED and instance.status != HomepageSection.STATUS_PUBLISHED:
            validated_data["published_at"] = timezone.now()
        return super().update(instance, validated_data)

    def create(self, validated_data):
        if validated_data.get("status") == HomepageSection.STATUS_PUBLISHED:
            validated_data["published_at"] = timezone.now()
        return super().create(validated_data)


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


class HomepageSectionAdminViewSet(viewsets.ModelViewSet):
    serializer_class = HomepageSectionAdminSerializer
    permission_classes = [StaffHomepagePermissions]
    queryset = HomepageSection.objects.prefetch_related("categories", "products").all()
    pagination_class = None
