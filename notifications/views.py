from django.db.models import Sum
from django.utils import timezone

from rest_framework import serializers
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.models import BloodUnit
from users.permissions import IsAdminRole

from .models import AdminNotification, LowStockThreshold
from .services import emergency_broadcast


class LowStockAlertsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.localdate()
        alerts = []

        thresholds = LowStockThreshold.objects.all().order_by(
            "blood_group"
        )

        for threshold in thresholds:
            available_quantity = (
                BloodUnit.objects.filter(
                    blood_group=threshold.blood_group,
                    expiry_date__gte=today,
                    quantity__gt=0,
                ).aggregate(total=Sum("quantity"))["total"]
                or 0
            )

            if available_quantity < threshold.minimum_quantity:
                message = (
                    f"Low stock for {threshold.blood_group}: "
                    f"{available_quantity} available, "
                    f"minimum is {threshold.minimum_quantity}."
                )

                alerts.append({
                    "blood_group": threshold.blood_group,
                    "available_quantity": available_quantity,
                    "minimum_quantity": threshold.minimum_quantity,
                    "message": message,
                })

                # Keep one current unread notification per blood group.
                existing = AdminNotification.objects.filter(
                    blood_group=threshold.blood_group,
                    is_read=False,
                ).order_by("-created_at").first()

                if existing is None:
                    AdminNotification.objects.create(
                        blood_group=threshold.blood_group,
                        message=message,
                        available_quantity=available_quantity,
                        minimum_quantity=threshold.minimum_quantity,
                    )
                elif (
                    existing.available_quantity != available_quantity
                    or existing.minimum_quantity != threshold.minimum_quantity
                    or existing.message != message
                ):
                    existing.message = message
                    existing.available_quantity = available_quantity
                    existing.minimum_quantity = threshold.minimum_quantity
                    existing.save(update_fields=[
                        "message",
                        "available_quantity",
                        "minimum_quantity",
                    ])

        return Response(alerts)


class EmergencyBroadcastSerializer(serializers.Serializer):
    blood_group = serializers.ChoiceField(
        choices=[
            "A+", "A-", "B+", "B-",
            "AB+", "AB-", "O+", "O-",
        ]
    )
    city = serializers.CharField(
        max_length=100,
        trim_whitespace=True,
    )
    details = serializers.CharField(
        max_length=2000,
        required=False,
        allow_blank=True,
    )

    def validate_city(self, value):
        if not value.strip():
            raise serializers.ValidationError(
                "City cannot be empty."
            )
        return value.strip()


class EmergencyBroadcastView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request):
        serializer = EmergencyBroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = emergency_broadcast(
            blood_group=serializer.validated_data["blood_group"],
            city=serializer.validated_data["city"],
            details=serializer.validated_data.get("details", ""),
        )

        return Response(result)
