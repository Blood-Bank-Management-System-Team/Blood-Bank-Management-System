
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsHospital, IsStaffOrAdmin
from inventory.models import BloodStock

from .models import BloodRequest
from .serializers import BloodRequestSerializer


class BloodRequestCreateView(generics.CreateAPIView):
    queryset = BloodRequest.objects.all()
    serializer_class = BloodRequestSerializer
    permission_classes = [IsHospital]

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)


class BloodRequestProcessView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def post(self, request, request_id):
        new_status = request.data.get("status")

        allowed_statuses = {
            BloodRequest.RequestStatus.APPROVED,
            BloodRequest.RequestStatus.REJECTED,
            BloodRequest.RequestStatus.FULFILLED,
        }

        if new_status not in allowed_statuses:
            return Response(
                {
                    "detail": (
                        "Status must be approved, rejected, or fulfilled."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                blood_request = (
                    BloodRequest.objects.select_for_update()
                    .get(request_id=request_id)
                )
            except BloodRequest.DoesNotExist:
                return Response(
                    {"detail": "Blood request not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if blood_request.status != BloodRequest.RequestStatus.PENDING:
                return Response(
                    {"detail": "Only pending requests can be processed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if new_status == BloodRequest.RequestStatus.FULFILLED:
                today = timezone.localdate()

                stock_rows = list(
                    BloodStock.objects.select_for_update()
                    .filter(
                        blood_group=blood_request.blood_group,
                        location__iexact=blood_request.location,
                        status=BloodStock.StockStatus.AVAILABLE,
                        expiry_date__gte=today,
                        available_units__gt=0,
                    )
                    .order_by("expiry_date", "pk")
                )

                total_units = sum(
                    stock.available_units for stock in stock_rows
                )

                if total_units < blood_request.units:
                    return Response(
                        {
                            "detail": "Insufficient available blood stock.",
                            "required_units": blood_request.units,
                            "available_units": total_units,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                remaining = blood_request.units

                for stock in stock_rows:
                    if remaining == 0:
                        break

                    deduction = min(stock.available_units, remaining)
                    stock.available_units -= deduction
                    stock.save(
                        update_fields=["available_units", "updated_at"]
                    )
                    remaining -= deduction

            blood_request.status = new_status
            blood_request.save(update_fields=["status"])

        return Response(
            {
                "request_id": str(blood_request.request_id),
                "blood_group": blood_request.blood_group,
                "units": blood_request.units,
                "location": blood_request.location,
                "status": blood_request.status,
            },
            status=status.HTTP_200_OK,
        )
