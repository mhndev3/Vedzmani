from rest_framework import serializers

from .models import User
from .phone import InvalidPhoneNumber, normalize_phone
from .services import CODE_LENGTH, normalize_code
from .national_id import InvalidNationalId, national_id_digest, normalize_national_id


class PhoneField(serializers.CharField):
    default_error_messages = {"invalid_phone": "Enter a valid Iranian mobile number."}

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 32)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_phone(value)
        except InvalidPhoneNumber:
            self.fail("invalid_phone")


class OTPRequestSerializer(serializers.Serializer):
    phone = PhoneField()


class OTPVerifySerializer(serializers.Serializer):
    phone = PhoneField()
    code = serializers.CharField(max_length=16, trim_whitespace=True)
    remember_me = serializers.BooleanField(required=False, default=False)

    def validate_code(self, value):
        value = normalize_code(value)
        if not (value.isascii() and value.isdigit() and len(value) == CODE_LENGTH):
            raise serializers.ValidationError("Enter the verification code.", code="invalid_code_format")
        return value


class CurrentUserSerializer(serializers.ModelSerializer):
    profile_complete = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "phone", "is_staff", "first_name", "last_name", "address",
            "postal_code", "profile_complete", "national_id_last4",
        ]
        read_only_fields = fields


class ProfileUpdateSerializer(serializers.ModelSerializer):
    national_id = serializers.CharField(max_length=32, trim_whitespace=True, write_only=True, required=False)
    postal_code = serializers.CharField(max_length=32, trim_whitespace=True)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "address", "postal_code", "national_id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not getattr(self.instance, "national_id_hash", None):
            self.fields["national_id"].required = True

    def validate_postal_code(self, value):
        value = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        if not value.isascii() or not value.isdigit() or len(value) != 10:
            raise serializers.ValidationError("Enter a 10-digit postal code.", code="invalid_postal_code")
        return value

    def validate_national_id(self, value):
        try:
            value = normalize_national_id(value)
        except InvalidNationalId:
            raise serializers.ValidationError("Enter a valid 10-digit national ID.", code="invalid_national_id") from None
        digest = national_id_digest(value)
        existing = User.objects.filter(national_id_hash=digest)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("This national ID is already linked to another account.", code="national_id_in_use")
        return value

    def validate_address(self, value):
        if not value.strip():
            raise serializers.ValidationError("Address is required.", code="blank")
        return value.strip()

    def update(self, instance, validated_data):
        national_id = validated_data.pop("national_id", None)
        for field, value in validated_data.items():
            setattr(instance, field, value.strip() if isinstance(value, str) else value)
        if national_id:
            instance.national_id_hash = national_id_digest(national_id)
            instance.national_id_last4 = national_id[-4:]
        instance.save()
        return instance

