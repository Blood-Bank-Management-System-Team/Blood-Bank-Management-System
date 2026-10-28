
from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsHospital, IsStaffOrAdmin

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

    # Supported filters and their corresponding model fields.
    FILTER_FIELDS = {
        "blood_group": "blood_group",
        "location": "bank_location",
        "expiry_date": "expiry_date",
        "collection_date": "collection_date",
    }

    # Supported sorting fields.
    SORT_FIELDS = {
        "blood_group": "blood_group",
        "location": "bank_location",
        "expiry_date": "expiry_date",
        "collection_date": "collection_date",
    }

    def get_queryset(self):
        queryset = BloodUnit.objects.all()
        params = self.request.query_params

        # Preserve the existing availability filter.
        if params.get("available", "").lower() == "true":
            queryset = queryset.filter(
                expiry_date__gte=timezone.localdate(),
                quantity__gt=0,
            )

        # Filter by blood group, location, expiry date,
        # and collection date.
        for param, field in self.FILTER_FIELDS.items():
            value = params.get(param, "").strip()

            if not value:
                continue

            if param in ("blood_group", "location"):
                queryset = queryset.filter(
                    **{f"{field}__iexact": value}
                )
            else:
                queryset = queryset.filter(
                    **{field: value}
                )

        # Sort by a supported field in ascending or descending order.
        sort_by = params.get("sort_by", "").strip()
        sort_order = params.get("sort_order", "asc").strip().lower()

        if sort_by in self.SORT_FIELDS and sort_order in ("asc", "desc"):
            field = self.SORT_FIELDS[sort_by]

            if sort_order == "desc":
                field = f"-{field}"

            queryset = queryset.order_by(field)

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
