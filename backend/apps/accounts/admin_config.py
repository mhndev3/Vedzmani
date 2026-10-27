from django.contrib.admin.apps import AdminConfig


class PasswordLoginAdminConfig(AdminConfig):
    """Replaces ``django.contrib.admin`` in INSTALLED_APPS (same app label) so ``admin.site`` is our site class.
    Every existing ``@admin.register`` keeps working unchanged."""

    default_site = "apps.accounts.admin_site.PasswordLoginAdminSite"
