"""Django Admin for the phone-identified user.

The stock ``UserAdmin`` assumes a ``username`` field, so the forms are rebuilt around ``phone``.
Authorization stays Django-native (is_staff / is_superuser / groups / permissions).

``OTPChallenge`` is deliberately NOT registered: it is authentication state (code hash + salt) with no
operational value for staff.
"""

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm
from django.urls import reverse
from django.utils.html import format_html

from .models import User
from .phone import InvalidPhoneNumber, normalize_phone


def _clean_phone(value: str) -> str:
    """Same normalizer as the API, so admin can never store a non-canonical phone."""
    try:
        return normalize_phone(value)
    except InvalidPhoneNumber as exc:
        raise forms.ValidationError(str(exc), code="invalid_phone")


class UserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("phone",)

    def clean_phone(self):
        return _clean_phone(self.cleaned_data["phone"])


class UserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = "__all__"

    def clean_phone(self):
        return _clean_phone(self.cleaned_data["phone"])


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeForm
    add_form = UserCreationForm

    list_display = ("phone", "is_active", "is_staff", "is_superuser", "date_joined", "last_login")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups")
    search_fields = ("phone",)
    ordering = ("-date_joined", "-id")
    filter_horizontal = ("groups", "user_permissions")
    readonly_fields = ("password_status", "last_login", "date_joined")

    # The password hash is never rendered; only whether a password exists.
    fieldsets = (
        (None, {"fields": ("phone", "password_status")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "usable_password", "password1", "password2")}),
    )

    @admin.display(description="Password")
    def password_status(self, obj):
        if not obj.pk:
            return "-"
        url = reverse("admin:auth_user_password_change", args=[obj.pk])
        if not obj.has_usable_password():
            return format_html('Not set (OTP login only) - <a href="{}">set password</a>', url)
        return format_html('Set - <a href="{}">change password</a>', url)

    def get_search_results(self, request, queryset, search_term):
        # Staff type 0912... / +98912...; the column stores the canonical form.
        try:
            search_term = normalize_phone(search_term)
        except InvalidPhoneNumber:
            pass
        return super().get_search_results(request, queryset, search_term)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            # No self-service privilege escalation through the user form.
            readonly += ["is_superuser", "groups", "user_permissions"]
        return readonly

    def has_change_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)
