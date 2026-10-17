"""Order PII permission.

`orders.view_order_pii` gates the unmasked customer phone and the delivery snapshot (recipient name, province,
city, address, postal code) in Django Admin.

Why it is registered by a `post_migrate` handler and not by `Meta.permissions`: adding `Meta.permissions` changes
the model state and would require a migration. This task must not create one. `post_migrate` fires on every
`migrate` run (new databases, existing databases, and the test database), so the permission exists everywhere the
schema does, and the handler is idempotent (`get_or_create`).

The permission is never granted here: nobody receives it automatically. Staff get it only when an administrator
assigns it to a user or group. Note that Django treats an active superuser as holding *every* permission
(`PermissionsMixin.has_perm`), so superusers can see PII; they still cannot mutate orders (see `admin.py`).
"""

from django.db import DEFAULT_DB_ALIAS, router

APP_LABEL = "orders"
PII_PERMISSION_CODENAME = "view_order_pii"
PII_PERMISSION = f"{APP_LABEL}.{PII_PERMISSION_CODENAME}"
PII_PERMISSION_NAME = "Can view order customer phone and delivery details (PII)"

# Order columns that are personal data. Used by the admin to keep them out of every surface.
ORDER_PII_FIELDS = ("customer_phone", "recipient_name", "province", "city", "address", "postal_code")


def has_order_pii_permission(user) -> bool:
    return bool(user is not None and user.is_active and user.has_perm(PII_PERMISSION))


def mask_phone(phone: str) -> str:
    """+989123456789 -> +9891****789 (enough to tell customers apart, not to contact them).

    Same output as the cart admin's helper; duplicated on purpose so this app does not import another app's
    `admin` module (importing it would couple admin registration order between apps).
    """
    phone = phone or ""
    return f"{phone[:5]}****{phone[-3:]}" if len(phone) > 8 else "****"


def create_order_pii_permission(sender=None, using=DEFAULT_DB_ALIAS, **kwargs):
    """post_migrate handler: make sure the `orders.view_order_pii` permission row exists."""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    if not router.allow_migrate_model(using, Permission):
        return
    # get_or_create (not the cached get_for_model): it is correct whether or not contenttypes already ran its own
    # post_migrate handler, regardless of handler order.
    content_type, _ = ContentType.objects.using(using).get_or_create(app_label=APP_LABEL, model="order")
    Permission.objects.using(using).get_or_create(
        content_type=content_type,
        codename=PII_PERMISSION_CODENAME,
        defaults={"name": PII_PERMISSION_NAME},
    )
