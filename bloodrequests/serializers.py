
from datetime import date

from rest_framework import serializers

from .models import BloodRequest


class BloodRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodRequest
        fields = [
            "request_id",
            "blood_group",
            "units",
            "location",
            "priority",
            "required_date",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "request_id",
            "status",
            "created_at",
        ]

    def validate_units(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Units must be at least 1."
            )
        return value

    def validate(self, attrs):
        priority = attrs.get(
            "priority",
            getattr(self.instance, "priority", None),
        )
        required_date = attrs.get(
            "required_date",
            getattr(self.instance, "required_date", None),
        )

        if priority == BloodRequest.Priority.SCHEDULED:
            if required_date is None:
                raise serializers.ValidationError({
                    "required_date": (
                        "A required date is needed for scheduled requests."
                    )
                })
            if required_date < date.today():
                raise serializers.ValidationError({
                    "required_date": "The required date cannot be in the past."
                })

        return attrs
