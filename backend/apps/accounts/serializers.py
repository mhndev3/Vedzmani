from rest_framework import serializers

from .models import User
from .phone import InvalidPhoneNumber, normalize_phone
from .services import CODE_LENGTH, normalize_code


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
    class Meta:
        model = User
        fields = ["id", "phone", "is_staff"]
        read_only_fields = fields

