"""Migration compatibility (Agent 11, Session 1): an order created BEFORE delivery details existed must survive
`orders.0002` with blank delivery columns and `unpaid`, on the real PostgreSQL test database.

The schema is moved back to `orders.0001`, a row is inserted with the historical model, the schema is migrated
forward again, and the row is read with the current model state. The `finally` always restores the latest schema.
"""

from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("orders", "0001_initial")]


@pytest.mark.django_db(transaction=True)
def test_existing_order_survives_the_delivery_details_migration():
    latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
    try:
        executor = MigrationExecutor(connection)
        executor.migrate(BEFORE)
        old_apps = executor.loader.project_state(BEFORE).apps
        old_user = old_apps.get_model("accounts", "User").objects.create(phone="+989120000077")
        old_order = old_apps.get_model("orders", "Order").objects.create(
            user=old_user, customer_phone=old_user.phone, total=Decimal("100")
        )
        assert not hasattr(old_order, "postal_code")  # really the pre-migration model

        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        new_apps = executor.loader.project_state(latest).apps
        migrated = new_apps.get_model("orders", "Order").objects.get(pk=old_order.pk)

        assert [migrated.recipient_name, migrated.province, migrated.city, migrated.address, migrated.postal_code] == [
            "", "", "", "", "",
        ]
        assert migrated.payment_status == "unpaid"
        assert migrated.status == "pending" and migrated.total == Decimal("100")
        assert migrated.customer_phone == "+989120000077"
    finally:
        MigrationExecutor(connection).migrate(latest)
