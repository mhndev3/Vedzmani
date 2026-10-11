"""Stock adjustment service: signed changes, audit rows, validation, rollback, row locking, real concurrency.

Concurrency tests use real threads and real PostgreSQL connections (`transaction=True`), like the order tests.
"""

import threading

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.db.models import QuerySet
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.cart.models import Cart, CartItem
from apps.catalog.models import VariantSize
from apps.inventory import services
from apps.inventory.models import InventoryAdjustment
from apps.inventory.services import InvalidAdjustment, StockWouldGoNegative, adjust_stock
from apps.orders.services import create_order
from tests.conftest import DELIVERY, new_phone

pytestmark = pytest.mark.django_db


@pytest.fixture
def actor(db):
    return get_user_model().objects.create_user(new_phone(), is_staff=True)


def stock(vs) -> int:
    return VariantSize.objects.values_list("stock_quantity", flat=True).get(pk=vs.pk)


def adjust(vs, change, reason="Cycle count", by=None):
    return adjust_stock(variant_size_id=vs.pk, quantity_change=change, reason=reason, created_by=by)


# --- behaviour -----------------------------------------------------------------------------
def test_positive_adjustment_increases_stock(make_variant_size, actor):
    vs = make_variant_size(stock=5)
    result = adjust(vs, 3, by=actor)
    assert stock(vs) == 8
    assert result.stock_after == 8


def test_negative_adjustment_decreases_stock(make_variant_size, actor):
    vs = make_variant_size(stock=5)
    result = adjust(vs, -2, by=actor)
    assert stock(vs) == 3
    assert result.stock_after == 3


def test_stock_can_be_removed_down_to_exactly_zero(make_variant_size, actor):
    vs = make_variant_size(stock=5)
    adjust(vs, -5, by=actor)
    assert stock(vs) == 0


def test_adjustment_only_touches_its_own_row(make_variant_size, actor):
    a, b = make_variant_size(stock=5), make_variant_size(stock=7)
    adjust(a, 1, by=actor)
    assert (stock(a), stock(b)) == (6, 7)


def test_updated_at_is_bumped(make_variant_size, actor):
    vs = make_variant_size(stock=5)
    before = VariantSize.objects.get(pk=vs.pk).updated_at
    adjust(vs, 1, by=actor)
    assert VariantSize.objects.get(pk=vs.pk).updated_at > before


# --- audit ---------------------------------------------------------------------------------
def test_audit_record_captures_who_what_why_when(make_variant_size, actor):
    vs = make_variant_size(stock=5)
    started = timezone.now()
    adjust(vs, -2, reason="  Damaged in storage  ", by=actor)

    record = InventoryAdjustment.objects.get()
    assert record.variant_size_id == vs.pk
    assert record.quantity_change == -2
    assert record.stock_after == 3
    assert record.reason == "Damaged in storage"  # trimmed
    assert record.created_by == actor
    assert started <= record.created_at <= timezone.now()


def test_actor_is_optional_for_system_adjustments(make_variant_size):
    vs = make_variant_size(stock=1)
    adjust(vs, 1, by=None)
    assert InventoryAdjustment.objects.get().created_by is None


def test_each_adjustment_gets_its_own_row_in_order(make_variant_size, actor):
    vs = make_variant_size(stock=0)
    for change in (5, -2, 10):
        adjust(vs, change, by=actor)
    rows = list(InventoryAdjustment.objects.filter(variant_size=vs).order_by("id"))
    assert [(r.quantity_change, r.stock_after) for r in rows] == [(5, 5), (-2, 3), (10, 13)]


# --- rejection -----------------------------------------------------------------------------
def test_adjustment_that_would_go_negative_is_rejected(make_variant_size, actor):
    vs = make_variant_size(stock=2)
    with pytest.raises(StockWouldGoNegative) as caught:
        adjust(vs, -3, by=actor)
    assert caught.value.status_code == 409 and caught.value.detail.code == "insufficient_stock"
    assert stock(vs) == 2
    assert not InventoryAdjustment.objects.exists()


def test_removing_from_empty_stock_is_rejected(make_variant_size, actor):
    vs = make_variant_size(stock=0)
    with pytest.raises(StockWouldGoNegative):
        adjust(vs, -1, by=actor)
    assert stock(vs) == 0 and not InventoryAdjustment.objects.exists()


@pytest.mark.parametrize("change", [0, True, 1.5, "3", None])
def test_invalid_quantity_change_is_rejected(make_variant_size, actor, change):
    vs = make_variant_size(stock=5)
    with pytest.raises(InvalidAdjustment):
        adjust(vs, change, by=actor)
    assert stock(vs) == 5 and not InventoryAdjustment.objects.exists()


@pytest.mark.parametrize("reason", ["", "   ", None, 7, "x" * 256])
def test_missing_or_invalid_reason_is_rejected(make_variant_size, actor, reason):
    vs = make_variant_size(stock=5)
    with pytest.raises(InvalidAdjustment):
        adjust(vs, 1, reason=reason, by=actor)
    assert stock(vs) == 5 and not InventoryAdjustment.objects.exists()


def test_reason_at_the_length_limit_is_accepted(make_variant_size, actor):
    vs = make_variant_size(stock=5)
    adjust(vs, 1, reason="x" * 255, by=actor)
    assert InventoryAdjustment.objects.get().reason == "x" * 255


@pytest.mark.parametrize("variant_size_id", [0, 10**12, "abc", None, True])
def test_unknown_variant_size_is_rejected(actor, variant_size_id):
    with pytest.raises(InvalidAdjustment):
        adjust_stock(variant_size_id=variant_size_id, quantity_change=1, reason="x", created_by=actor)
    assert not InventoryAdjustment.objects.exists()


def test_change_beyond_the_database_range_is_rejected_not_a_crash(make_variant_size, actor):
    vs = make_variant_size(stock=5)
    for change in (services.MAX_STOCK + 1, services.MAX_STOCK):  # out of range, then overflows the column
        with pytest.raises(InvalidAdjustment):
            adjust(vs, change, by=actor)
    assert stock(vs) == 5 and not InventoryAdjustment.objects.exists()


# --- locking + query shape -------------------------------------------------------------------
def test_service_locks_the_variant_size_row_and_uses_three_queries(make_variant_size, actor):
    vs = make_variant_size(stock=5)
    with CaptureQueriesContext(connection) as ctx:
        adjust(vs, 2, by=actor)
    statements = [q["sql"] for q in ctx.captured_queries if not q["sql"].startswith(("SAVEPOINT", "RELEASE"))]
    assert len(statements) == 3, statements  # lock+read, guarded update, audit insert
    assert statements[0].startswith("SELECT") and 'FOR UPDATE OF "catalog_variantsize"' in statements[0]
    assert statements[1].startswith("UPDATE") and statements[2].startswith("INSERT")


# --- rollback ------------------------------------------------------------------------------
@pytest.mark.django_db(transaction=True)
def test_failure_creating_the_audit_row_rolls_back_the_stock_change(make_variant_size, actor, monkeypatch):
    vs = make_variant_size(stock=5)

    def boom(*args, **kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(InventoryAdjustment.objects, "create", boom)  # runs after the stock UPDATE
    with pytest.raises(RuntimeError):
        adjust(vs, 4, by=actor)

    assert stock(vs) == 5
    assert not InventoryAdjustment.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_failure_updating_stock_leaves_no_audit_row(make_variant_size, actor, monkeypatch):
    vs = make_variant_size(stock=5)

    def boom(*args, **kwargs):
        raise RuntimeError("stock update failed")

    monkeypatch.setattr(QuerySet, "update", boom)
    with pytest.raises(RuntimeError):
        adjust(vs, 4, by=actor)
    monkeypatch.undo()

    assert stock(vs) == 5
    assert not InventoryAdjustment.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_rejected_adjustment_inside_an_outer_transaction_does_not_poison_it(make_variant_size, actor):
    vs = make_variant_size(stock=5)
    with transaction.atomic():
        adjust(vs, 1, by=actor)
        with pytest.raises(StockWouldGoNegative):
            adjust(vs, -100, by=actor)
        adjust(vs, 1, by=actor)  # the outer transaction is still usable
    assert stock(vs) == 7 and InventoryAdjustment.objects.count() == 2


# --- compatibility with order checkout (unchanged) ----------------------------------------------
def test_order_checkout_still_decrements_stock_and_is_not_an_adjustment(make_variant_size, actor):
    vs = make_variant_size(stock=10)
    adjust(vs, 5, by=actor)  # 15
    customer = get_user_model().objects.create_user(new_phone())
    CartItem.objects.create(cart=Cart.objects.create(user=customer), variant_size=vs, quantity=4)

    order = create_order(customer, DELIVERY)

    assert stock(vs) == 11
    assert order.items.get().quantity == 4
    assert InventoryAdjustment.objects.count() == 1  # checkout is recorded by the order, not by an adjustment
    adjust(vs, -1, by=actor)
    assert stock(vs) == 10


# --- concurrency: real threads, real PostgreSQL connections ----------------------------------------
def _run_concurrently(calls):
    """Run each zero-argument callable in its own thread (own DB connection), released together by a barrier."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def worker(index):
        try:
            barrier.wait(timeout=15)
            results[index] = ("ok", calls[index]())
        except Exception as exc:  # noqa: BLE001 - classified by the assertions
            results[index] = ("error", exc)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(len(calls))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results


@pytest.mark.django_db(transaction=True)
def test_concurrent_removals_never_oversell(make_variant_size, actor):
    vs = make_variant_size(stock=5)

    results = _run_concurrently([lambda: adjust(vs, -1, by=actor) for _ in range(8)])

    ok = [r for kind, r in results if kind == "ok"]
    errors = [r for kind, r in results if kind == "error"]
    assert len(ok) == 5 and len(errors) == 3
    assert all(isinstance(e, StockWouldGoNegative) for e in errors)
    assert stock(vs) == 0
    rows = InventoryAdjustment.objects.filter(variant_size=vs)
    assert rows.count() == 5
    assert sorted(r.stock_after for r in rows) == [0, 1, 2, 3, 4]


@pytest.mark.django_db(transaction=True)
def test_concurrent_mixed_adjustments_keep_stock_and_audit_consistent(make_variant_size, actor):
    vs = make_variant_size(stock=10)
    calls = [lambda: adjust(vs, 2, by=actor) for _ in range(6)] + [lambda: adjust(vs, -3, by=actor) for _ in range(6)]

    results = _run_concurrently(calls)

    assert all(kind == "ok" or isinstance(r, StockWouldGoNegative) for kind, r in results), results
    rows = list(InventoryAdjustment.objects.filter(variant_size=vs).order_by("id"))
    assert len(rows) == sum(1 for kind, _ in results if kind == "ok")
    assert stock(vs) == 10 + sum(r.quantity_change for r in rows) >= 0
    balance = 10
    for row in rows:  # the row lock serializes adjustments, so id order is the real order of application
        balance += row.quantity_change
        assert row.stock_after == balance >= 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_adjustment_and_checkout_do_not_lose_updates(make_variant_size, actor):
    vs = make_variant_size(stock=10)
    customers = [get_user_model().objects.create_user(new_phone()) for _ in range(4)]
    for customer in customers:
        CartItem.objects.create(cart=Cart.objects.create(user=customer), variant_size=vs, quantity=1)

    calls = [lambda c=c: create_order(c, DELIVERY) for c in customers] + [lambda: adjust(vs, 5, by=actor) for _ in range(4)]
    results = _run_concurrently(calls)

    assert all(kind == "ok" for kind, _ in results), results
    assert stock(vs) == 10 - 4 + 20  # every checkout (-1) and every adjustment (+5) was applied exactly once
    assert InventoryAdjustment.objects.count() == 4
