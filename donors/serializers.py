from drf_spectacular.utils import extend_schema_field

from rest_framework import serializers

from .models import DonationRecord, DonorProfile


class DonorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DonorProfile
        fields = (
            "id",
            "blood_group",
            "date_of_birth",
            "weight_kg",
            "gender",
            "address",
            "city",
            "last_donation_date",
            "has_chronic_illness",
            "on_medication",
            "recent_surgery_or_tattoo_6_months",
            "recent_illness_or_fever_2_weeks",
            "is_pregnant_or_breastfeeding",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class EligibilitySerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    reasons = serializers.ListField(child=serializers.CharField())
    next_eligible_date = serializers.DateField()


class DonorListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username")
    phone = serializers.CharField(source="user.phone")
    eligible = serializers.SerializerMethodField()
    next_eligible_date = serializers.SerializerMethodField()

    class Meta:
        model = DonorProfile
        fields = (
            "id",
            "username",
            "phone",
            "blood_group",
            "city",
            "last_donation_date",
            "eligible",
            "next_eligible_date",
        )

    @extend_schema_field(serializers.BooleanField)
    def get_eligible(self, obj) -> bool:
        return obj.eligibility().eligible

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_next_eligible_date(self, obj):
        return obj.eligibility().next_eligible_date


class DonationRecordSerializer(serializers.ModelSerializer):
    recorded_by = serializers.CharField(source="recorded_by.username", read_only=True)

    class Meta:
        model = DonationRecord
        fields = ("id", "donation_date", "blood_bank_location", "units", "recorded_by", "notes", "created_at")
        read_only_fields = ("id", "recorded_by", "created_at")
