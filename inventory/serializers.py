
from rest_framework import serializers

from .models import BloodUnit


class BloodUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = BloodUnit
        fields = [
            "id",
            "blood_group",
            "quantity",
            "collection_date",
            "expiry_date",
            "bank_location",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        collection_date = attrs.get(
            "collection_date",
            getattr(self.instance, "collection_date", None),
        )
        expiry_date = attrs.get(
            "expiry_date",
            getattr(self.instance, "expiry_date", None),
        )

        if collection_date and expiry_date and expiry_date <= collection_date:
            raise serializers.ValidationError({
                "expiry_date": "Expiry date must be after collection date."
            })

        return attrs
