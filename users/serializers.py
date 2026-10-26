from django.core.validators import RegexValidator
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User

SELF_REGISTER_ROLES = (User.Role.DONOR, User.Role.HOSPITAL)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    role = serializers.ChoiceField(
        choices=[(r.value, r.label) for r in SELF_REGISTER_ROLES],
        default=User.Role.DONOR,
    )
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "role", "phone")
        read_only_fields = ("id",)

    def validate(self, attrs):
        candidate = User(**{k: v for k, v in attrs.items() if k != "password"})
        validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("username", "email", "role", "phone")
        read_only_fields = fields


PHONE_RE = RegexValidator(r"^[6-9]\d{9}$", "Enter a valid 10-digit Indian mobile number.")


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=False, allow_blank=True, validators=[PHONE_RE])

    class Meta:
        model = User
        fields = ("username", "role", "first_name", "last_name", "email", "phone")
        read_only_fields = ("username", "role")
        extra_kwargs = {"first_name": {"required": False}, "last_name": {"required": False}}


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["role"] = self.user.role
        data["username"] = self.user.username
        return data
