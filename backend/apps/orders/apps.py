from django.apps import AppConfig
from django.db.models.signals import post_migrate


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.orders"
    label = "orders"

    def ready(self):
        from .permissions import create_order_pii_permission

        # Registers `orders.view_order_pii` without a model migration (see permissions.py).
        post_migrate.connect(
            create_order_pii_permission, sender=self, dispatch_uid="orders.create_order_pii_permission"
        )
