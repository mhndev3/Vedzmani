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



class CustomerProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(max_length=150, trim_whitespace=True)
    last_name = serializers.CharField(max_length=150, trim_whitespace=True)
    address = serializers.CharField(max_length=1000, trim_whitespace=True)
    postal_code = serializers.CharField(max_length=20, trim_whitespace=True)
    national_code = serializers.CharField(max_length=32, trim_whitespace=True)
    is_complete = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "phone", "first_name", "last_name", "address", "postal_code", "national_code", "is_complete"]
        read_only_fields = ["id", "phone", "is_complete"]

    def validate_national_code(self, value):
        digits = value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        if len(digits) != 10 or not digits.isascii() or not digits.isdigit():
            raise serializers.ValidationError("کد ملی باید دقیقاً ۱۰ رقم باشد.", code="invalid_national_code")
        duplicate = User.objects.filter(national_code=digits)
        if self.instance is not None:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError("این کد ملی قبلاً ثبت شده است.", code="unique")
        return digits

    def get_is_complete(self, obj):
        return bool(obj.first_name and obj.last_name and obj.address and obj.postal_code and obj.national_code)
