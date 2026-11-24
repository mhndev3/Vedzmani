# Add immutable revision histories for homepage banners and storefront theme.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def seed_banner_and_theme_baselines(apps, schema_editor):
    HomepageBanner = apps.get_model("catalog", "HomepageBanner")
    HomepageBannerRevision = apps.get_model("catalog", "HomepageBannerRevision")
    StorefrontTheme = apps.get_model("catalog", "StorefrontTheme")
    StorefrontThemeRevision = apps.get_model("catalog", "StorefrontThemeRevision")
    database = schema_editor.connection.alias

    for banner in HomepageBanner.objects.using(database).all().iterator():
        snapshot = {
            "title": banner.title,
            "subtitle": banner.subtitle,
            "alt_text": banner.alt_text,
            "desktop_image": banner.desktop_image.name,
            "mobile_image": banner.mobile_image.name,
            "cta_label": banner.cta_label,
            "cta_url": banner.cta_url,
            "position": banner.position,
            "status": banner.status,
            "starts_at": banner.starts_at.isoformat() if banner.starts_at else None,
            "ends_at": banner.ends_at.isoformat() if banner.ends_at else None,
        }
        HomepageBannerRevision.objects.using(database).create(
            banner_id=banner.pk, snapshot=snapshot, action="baseline", created_by_id=None,
        )

    theme, _ = StorefrontTheme.objects.using(database).get_or_create(pk=1)
    StorefrontThemeRevision.objects.using(database).create(
        theme_id=theme.pk,
        snapshot={
            "draft_settings": theme.draft_settings,
            "published_settings": theme.published_settings,
            "published_at": theme.published_at.isoformat() if theme.published_at else None,
        },
        action="baseline",
        created_by_id=None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0017_homepage_section_revision"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HomepageBannerRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("snapshot", models.JSONField()),
                ("action", models.CharField(choices=[("baseline", "Baseline"), ("created", "Created"), ("updated", "Updated"), ("rollback", "Rollback")], max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("banner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="catalog.homepagebanner")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="homepage_banner_revisions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["banner", "-created_at"], name="home_banner_rev_idx")],
            },
        ),
        migrations.CreateModel(
            name="StorefrontThemeRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("snapshot", models.JSONField()),
                ("action", models.CharField(choices=[("baseline", "Baseline"), ("draft_saved", "Draft saved"), ("published", "Published"), ("rollback", "Rollback")], max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("theme", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="catalog.storefronttheme")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="storefront_theme_revisions", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [models.Index(fields=["theme", "-created_at"], name="store_theme_rev_idx")],
            },
        ),
        migrations.RunPython(seed_banner_and_theme_baselines, migrations.RunPython.noop),
    ]
