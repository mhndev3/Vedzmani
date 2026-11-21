"""Permission-checked shipping method and tariff configuration API.

This is a dormant admin configuration surface until carrier tariffs are confirmed and a separate checkout
change snapshots the selected method and price on each order.
"""
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import DjangoModelPermissions

from apps.catalog.pagination import CatalogPagination
from .models import ShippingMethod


class StaffShippingPermissions(DjangoModelPermissions):
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
        return bool(user and user.is_authenticated and user.is_active and user.is_staff
                    and super().has_permission(request, view))


class ShippingMethodAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = [
            "id", "code", "name", "provider", "pricing_mode", "amount_toman",
            "service_area", "min_delivery_days", "max_delivery_days", "description",
            "is_active", "position", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = self.instance
        pricing_mode = attrs.get("pricing_mode", getattr(instance, "pricing_mode", ShippingMethod.QUOTE))
        amount = attrs.get("amount_toman", getattr(instance, "amount_toman", None))
        minimum = attrs.get("min_delivery_days", getattr(instance, "min_delivery_days", None))
        maximum = attrs.get("max_delivery_days", getattr(instance, "max_delivery_days", None))

        if pricing_mode == ShippingMethod.FIXED and amount is None:
            raise serializers.ValidationError({"amount_toman": "برای تعرفه ثابت، مبلغ به تومان الزامی است."})
        if pricing_mode == ShippingMethod.QUOTE and amount is not None:
            raise serializers.ValidationError({"amount_toman": "برای استعلام از شرکت حمل، مبلغ ثابت باید خالی باشد."})
        if minimum is not None and maximum is not None and maximum < minimum:
            raise serializers.ValidationError({"max_delivery_days": "حداکثر زمان ارسال نمی‌تواند کمتر از حداقل باشد."})
        return attrs


class ShippingMethodAdminViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ShippingMethod.objects.all()
    serializer_class = ShippingMethodAdminSerializer
    permission_classes = [StaffShippingPermissions]
    pagination_class = CatalogPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        provider = self.request.query_params.get("provider")
        if provider:
            queryset = queryset.filter(provider=provider)
        active = self.request.query_params.get("is_active")
        if active in {"true", "false"}:
            queryset = queryset.filter(is_active=(active == "true"))
        return queryset
