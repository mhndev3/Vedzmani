"""Staff-only draft and public published storefront theme endpoints."""
import re

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import StorefrontTheme, StorefrontThemeRevision, default_storefront_theme_settings


def theme_snapshot(theme):
    return {
        "draft_settings": theme.draft_settings,
        "published_settings": theme.published_settings,
        "published_at": theme.published_at.isoformat() if theme.published_at else None,
    }


def record_theme_revision(theme, actor, action):
    return StorefrontThemeRevision.objects.create(
        theme=theme,
        snapshot=theme_snapshot(theme),
        action=action,
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
    )


class StorefrontThemeRevisionSerializer(serializers.ModelSerializer):
    created_by_label = serializers.SerializerMethodField()

    class Meta:
        model = StorefrontThemeRevision
        fields = ["id", "action", "snapshot", "created_by_label", "created_at"]
        read_only_fields = fields

    def get_created_by_label(self, obj):
        if obj.created_by is None:
            return "سیستم"
        return obj.created_by.phone or obj.created_by.get_username()


class StorefrontThemeRevisionView(APIView):
    permission_classes = [StaffThemePermission]

    @transaction.atomic
    def get(self, request):
        theme, created = StorefrontTheme.objects.get_or_create(pk=1)
        if created:
            record_theme_revision(theme, request.user, StorefrontThemeRevision.ACTION_BASELINE)
        rows = theme.revisions.select_related("created_by").all()
        return Response(StorefrontThemeRevisionSerializer(rows, many=True).data)

    @transaction.atomic
    @transaction.atomic
    def post(self, request):
        revision_id = request.data.get("revision_id")
        if not str(revision_id or "").isdigit():
            return Response({"revision_id": "شناسه نسخه معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST)
        theme, _ = StorefrontTheme.objects.get_or_create(pk=1)
        revision = theme.revisions.filter(pk=int(revision_id)).first()
        if revision is None:
            return Response({"revision_id": "نسخه انتخاب‌شده معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST)
        settings = revision.snapshot.get("draft_settings")
        validator = StorefrontThemeSettingsSerializer(data={"settings": settings})
        validator.is_valid(raise_exception=True)
        theme.draft_settings = validator.validated_data["settings"]
        theme.updated_by = request.user
        theme.save(update_fields=["draft_settings", "updated_by", "updated_at"])
        record_theme_revision(theme, request.user, StorefrontThemeRevision.ACTION_ROLLBACK)
        return Response({"draft_settings": theme.draft_settings, "published_settings": theme.published_settings})


class StorefrontThemeSettingsSerializer(serializers.Serializer):
    settings = serializers.JSONField()

    def validate_settings(self, value):
        required = {
            "primary", "primary_foreground", "accent", "accent_foreground",
            "font", "radius", "motion",
        }
        if not isinstance(value, dict) or set(value) != required:
            raise serializers.ValidationError("ساختار تنظیمات قالب معتبر نیست.")
        for key in ("primary", "primary_foreground", "accent", "accent_foreground"):
            if not isinstance(value[key], str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value[key]):
                raise serializers.ValidationError({key: "رنگ باید کد HEX شش‌رقمی باشد."})
        choices = {
            "font": {"system", "persian-modern", "classic"},
            "radius": {"compact", "medium", "rounded"},
            "motion": {"none", "subtle", "standard"},
        }
        for key, allowed in choices.items():
            if value[key] not in allowed:
                raise serializers.ValidationError({key: "مقدار انتخاب‌شده پشتیبانی نمی‌شود."})
        return value


class StaffThemePermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active or not user.is_staff:
            return False
        permission = "catalog.view_storefronttheme" if request.method == "GET" else "catalog.change_storefronttheme"
        return user.has_perm(permission)


class StorefrontThemeAdminView(APIView):
    permission_classes = [StaffThemePermission]

    def get_object(self, create=False):
        theme = StorefrontTheme.objects.filter(pk=1).first()
        if theme is None and create:
            theme = StorefrontTheme.objects.create(pk=1)
        return theme

    def get(self, request):
        theme = self.get_object()
        defaults = default_storefront_theme_settings()
        return Response({
            "draft_settings": theme.draft_settings if theme else defaults,
            "published_settings": theme.published_settings if theme else defaults,
            "updated_at": theme.updated_at if theme else None,
            "published_at": theme.published_at if theme else None,
        })

    @transaction.atomic
    def patch(self, request):
        serializer = StorefrontThemeSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        theme = self.get_object(create=True)
        theme.draft_settings = serializer.validated_data["settings"]
        theme.updated_by = request.user
        theme.save(update_fields=["draft_settings", "updated_by", "updated_at"])
        record_theme_revision(theme, request.user, StorefrontThemeRevision.ACTION_DRAFT)
        return Response({"draft_settings": theme.draft_settings, "updated_at": theme.updated_at})

    def post(self, request):
        if request.data.get("action") != "publish":
            return Response({"detail": "عملیات معتبر نیست."}, status=status.HTTP_400_BAD_REQUEST)
        theme = self.get_object(create=True)
        theme.published_settings = theme.draft_settings
        theme.published_at = timezone.now()
        theme.updated_by = request.user
        theme.save(update_fields=["published_settings", "published_at", "updated_by", "updated_at"])
        record_theme_revision(theme, request.user, StorefrontThemeRevision.ACTION_PUBLISHED)
        return Response({
            "published_settings": theme.published_settings,
            "published_at": theme.published_at,
        })


class StorefrontThemePublicView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        settings = StorefrontTheme.objects.filter(pk=1).values_list("published_settings", flat=True).first()
        return Response({"settings": settings or default_storefront_theme_settings()})
