
from rest_framework import serializers

from .models import BloodStock


class BloodAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodStock
        fields = (
            "blood_group",
            "location",
            "available_units",
            "expiry_date",
        )
