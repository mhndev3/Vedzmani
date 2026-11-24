"""Validation helpers for category-defined optional product fields."""
import re
from decimal import Decimal, InvalidOperation

from rest_framework import serializers


_FIELD_KEY = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_FIELD_TYPES = {"text", "number"}


def clean_optional_marker(value):
    """Treat the exact admin placeholder // as an intentionally blank optional value."""
    if value is None:
        return ""
    if isinstance(value, str):
        normalized = value.strip()
        return "" if normalized == "//" else normalized
    return value


def validate_product_field_schema(value):
    if not isinstance(value, list):
        raise serializers.ValidationError("فهرست فیلدهای اختصاصی دسته‌بندی باید آرایه باشد.")
    if len(value) > 20:
        raise serializers.ValidationError("هر دسته‌بندی حداکثر می‌تواند ۲۰ فیلد اختصاصی داشته باشد.")

    normalized = []
    seen_keys = set()
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise serializers.ValidationError({index: "تعریف فیلد معتبر نیست."})
        key = str(item.get("key", "")).strip()
        label = str(item.get("label", "")).strip()
        field_type = str(item.get("type", "text")).strip()
        unit = clean_optional_marker(item.get("unit", ""))
        unit = "" if unit is None else str(unit).strip()
        required = item.get("required", False)

        if not _FIELD_KEY.fullmatch(key):
            raise serializers.ValidationError({index: {"key": "شناسه فیلد باید با حروف انگلیسی کوچک شروع شود و فقط حروف، عدد و زیرخط داشته باشد."}})
        if key in seen_keys:
            raise serializers.ValidationError({index: {"key": "شناسه فیلد تکراری است."}})
        if not label or len(label) > 80:
            raise serializers.ValidationError({index: {"label": "عنوان فیلد الزامی است و حداکثر ۸۰ نویسه دارد."}})
        if field_type not in _FIELD_TYPES:
            raise serializers.ValidationError({index: {"type": "نوع فیلد فقط می‌تواند متنی یا عددی باشد."}})
        if len(unit) > 24:
            raise serializers.ValidationError({index: {"unit": "واحد فیلد حداکثر ۲۴ نویسه دارد."}})
        if not isinstance(required, bool):
            raise serializers.ValidationError({index: {"required": "وضعیت اجباری بودن باید درست یا نادرست باشد."}})

        seen_keys.add(key)
        normalized.append({
            "key": key,
            "label": label,
            "type": field_type,
            "unit": unit,
            "required": required,
        })
    return normalized


def clean_product_attributes(category, value, *, reject_unknown=True, enforce_required=True):
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise serializers.ValidationError("مشخصات اختصاصی محصول باید به‌صورت شیء ارسال شوند.")

    schema = validate_product_field_schema(category.product_fields or [])
    definitions = {field["key"]: field for field in schema}
    unknown = set(value) - set(definitions)
    if reject_unknown and unknown:
        raise serializers.ValidationError({
            "attributes": "یک یا چند فیلد با دسته‌بندی انتخاب‌شده هم‌خوانی ندارد."
        })

    cleaned = {}
    for key, definition in definitions.items():
        raw = value.get(key, "")
        if isinstance(raw, (dict, list, bool)):
            raise serializers.ValidationError({"attributes": {key: "مقدار فیلد باید متنی یا عددی باشد."}})
        item = clean_optional_marker(raw)
        item = "" if item is None else str(item).strip()
        if enforce_required and definition["required"] and not item:
            raise serializers.ValidationError({"attributes": {key: f"فیلد «{definition['label']}» الزامی است."}})
        if definition["type"] == "number" and item:
            try:
                numeric = Decimal(item)
                if not numeric.is_finite():
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                raise serializers.ValidationError({"attributes": {key: f"فیلد «{definition['label']}» باید عددی باشد."}})
        cleaned[key] = item
    return cleaned
