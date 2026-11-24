"""Staff-only administration for homepage banner collections."""
from rest_framework import mixins, serializers, viewsets
from rest_framework.permissions import DjangoModelPermissions

from .models import HomepageBannerGroup


class BannerGroupAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomepageBannerGroup
        fields = ["id", "name", "slug", "position", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class StaffBannerGroupPermissions(DjangoModelPermissions):
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
        return bool(
            user and user.is_authenticated and user.is_staff
            and request.method != "DELETE"
            and super().has_permission(request, view)
        )


class HomepageBannerGroupAdminViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Groups can be deactivated, not physically deleted, preserving banner history."""

    queryset = HomepageBannerGroup.objects.all()
    serializer_class = BannerGroupAdminSerializer
    permission_classes = [StaffBannerGroupPermissions]
    pagination_class = None
