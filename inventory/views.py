from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsHospital, IsStaffOrAdmin

from .compatibility import is_blood_compatible
from .models import BloodStock, BloodUnit
from .serializers import BloodAvailabilitySerializer, BloodUnitSerializer


class BloodAvailabilityView(APIView):
    permission_classes = [IsHospital]

    def get(self, request):
        blood_group = request.query_params.get(
            "blood_group", ""
        ).strip().upper()
        location = request.query_params.get("location", "").strip()

        valid_groups = BloodStock.BloodGroup.values

        if not blood_group or not location:
            return Response(
                {"detail": "Both blood_group and location are required."},
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


class BloodUnitListCreateView(generics.ListCreateAPIView):
    queryset = BloodUnit.objects.all()
    serializer_class = BloodUnitSerializer
    permission_classes = [IsStaffOrAdmin]

    def get_queryset(self):
        queryset = BloodUnit.objects.all()

        if self.request.query_params.get("available", "").lower() == "true":
            queryset = queryset.filter(
                expiry_date__gte=timezone.localdate(),
                quantity__gt=0,
            )

        return queryset

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
            updated_by=self.request.user,
        )


class BloodUnitDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = BloodUnit.objects.all()
    serializer_class = BloodUnitSerializer
    permission_classes = [IsStaffOrAdmin]

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)


class StockSummaryView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def get(self, request):
        stock = (
            BloodUnit.objects.filter(
                expiry_date__gte=timezone.localdate(),
                quantity__gt=0,
            )
            .values("blood_group", "bank_location")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("blood_group", "bank_location")
        )

        return Response(list(stock))

class CrossBankSearchView(APIView):
    """
    Search available, unexpired blood stock across all recorded locations.

    Results include stock whose donor blood group is compatible with the
    requested recipient blood group. The requested location is prioritised.
    """

    permission_classes = [IsHospital]

    def get(self, request):
        recipient_group = (
            request.query_params.get("blood_group", "").strip().upper()
        )
        location = request.query_params.get("location", "").strip()

        valid_groups = BloodStock.BloodGroup.values

        if not recipient_group or not location:
            return Response(
                {"detail": "Both blood_group and location are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if recipient_group not in valid_groups:
            return Response(
                {"detail": "Invalid blood group."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        compatible_groups = [
            donor_group
            for donor_group in valid_groups
            if is_blood_compatible(donor_group, recipient_group)
        ]

        today = timezone.localdate()

        stock_rows = (
            BloodStock.objects.filter(
                blood_group__in=compatible_groups,
                status=BloodStock.StockStatus.AVAILABLE,
                expiry_date__gte=today,
                available_units__gt=0,
            )
            .order_by("expiry_date", "location", "blood_group", "pk")
        )

        results = []
        for stock in stock_rows:
            results.append(
                {
                    "id": stock.pk,
                    "blood_group": stock.blood_group,
                    "location": stock.location,
                    "available_units": stock.available_units,
                    "expiry_date": stock.expiry_date.isoformat(),
                    "is_requested_location": (
                        stock.location.casefold() == location.casefold()
                    ),
                }
            )

        results.sort(
            key=lambda item: (
                not item["is_requested_location"],
                item["expiry_date"],
                item["location"].casefold(),
                item["blood_group"],
                item["id"],
            )
        )

        return Response(
            {
                "recipient_blood_group": recipient_group,
                "requested_location": location,
                "results": results,
                "total_units": sum(
                    item["available_units"] for item in results
                ),
            },
            status=status.HTTP_200_OK,
        )