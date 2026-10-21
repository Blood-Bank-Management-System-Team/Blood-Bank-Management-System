
from django.db.models import Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsHospital

from .models import BloodStock


class BloodAvailabilityView(APIView):
    permission_classes = [IsHospital]

    def get(self, request):
        blood_group = request.query_params.get("blood_group", "").strip().upper()
        location = request.query_params.get("location", "").strip()

        valid_groups = BloodStock.BloodGroup.values

        if not blood_group or not location:
            return Response(
                {
                    "detail": (
                        "Both blood_group and location are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if blood_group not in valid_groups:
            return Response(
                {"detail": "Invalid blood group."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = timezone.localdate()

        matching_stock = BloodStock.objects.filter(
            blood_group=blood_group,
            location__iexact=location,
            status=BloodStock.StockStatus.AVAILABLE,
            expiry_date__gte=today,
        )

        total_units = matching_stock.aggregate(
            total=Sum("available_units")
        )["total"] or 0

        if total_units == 0:
            return Response(
                {
                    "detail": (
                        "No available blood stock found "
                        "for this blood group and location."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                "blood_group": blood_group,
                "location": location,
                "available_units": total_units,
                "status": "available",
            },
            status=status.HTTP_200_OK,
        )
