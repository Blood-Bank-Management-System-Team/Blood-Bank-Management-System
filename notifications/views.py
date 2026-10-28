
from django.db.models import Sum
from django.utils import timezone
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.models import BloodUnit
from .models import AdminNotification, LowStockThreshold


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
