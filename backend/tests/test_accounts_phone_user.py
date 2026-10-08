import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.accounts.phone import InvalidPhoneNumber, normalize_phone

CANONICAL = "+989123456789"


@pytest.mark.parametrize(
    "raw",
    [
        "09123456789",
        "9123456789",
        "989123456789",
        "+989123456789",
        "00989123456789",
        " 0912 345 6789 ",
        "0912-345-6789",
        "+98 912 345 6789",
        "۰۹۱۲۳۴۵۶۷۸۹",
        "٠٩١٢٣٤٥٦٧٨٩",
    ],
)
def test_equivalent_formats_normalize_identically(raw):
    assert normalize_phone(raw) == CANONICAL


def test_bare_national_number_starting_with_98_is_not_read_as_country_code():
    assert normalize_phone("9812345678") == "+989812345678"


@pytest.mark.parametrize(
    "raw",
    ["", "abc", "0912345678", "091234567890", "08123456789", "+19123456789", "09123x56789", None, 9123456789],
)
def test_invalid_phones_rejected(raw):
    with pytest.raises(InvalidPhoneNumber):
        normalize_phone(raw)


@pytest.mark.django_db
def test_create_user_with_valid_phone_is_normalized():
    user = User.objects.create_user("0912 345 6789")
    user.refresh_from_db()
    assert user.phone == CANONICAL
    assert user.is_active and not user.is_staff and not user.is_superuser
    assert not user.has_usable_password()  # customers authenticate by OTP only


@pytest.mark.django_db
def test_equivalent_formats_cannot_create_duplicate_users():
    first, created_first = User.objects.get_or_create_by_phone("09123456789")
    second, created_second = User.objects.get_or_create_by_phone("+98 912 345 6789")
    assert (created_first, created_second) == (True, False)
    assert first.pk == second.pk
    assert User.objects.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user("989123456789")


@pytest.mark.django_db
def test_model_save_rejects_non_phone_and_normalizes_direct_construction():
    with pytest.raises(InvalidPhoneNumber):
        User(phone="not-a-phone").save()
    user = User(phone="09123456789")
    user.save()
    assert user.phone == CANONICAL


@pytest.mark.django_db
def test_db_constraint_blocks_non_canonical_phone_even_bypassing_save():
    user = User.objects.create_user(CANONICAL)
    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.filter(pk=user.pk).update(phone="09123456789")


@pytest.mark.django_db
def test_superuser_uses_django_native_permissions():
    with pytest.raises(ValueError):
        User.objects.create_superuser(CANONICAL)
    admin = User.objects.create_superuser(CANONICAL, password="correct-horse-battery")
    assert admin.is_staff and admin.is_superuser and admin.has_perm("accounts.view_user")
    customer = User.objects.create_user("09120000001")
    assert not customer.has_perm("accounts.view_user")
