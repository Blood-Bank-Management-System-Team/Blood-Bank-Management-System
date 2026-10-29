from django.db.models import Sum
from django.utils import timezone

from rest_framework import generics, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    inline_serializer,
)

from users.permissions import IsHospital, IsStaffOrAdmin
from .models import BloodStock, BloodUnit
from .serializers import BloodAvailabilitySerializer, BloodUnitSerializer


class BloodAvailabilityView(APIView):
    permission_classes = [IsHospital]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="blood_group",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Blood group to search for, such as O+ or A-.",
            ),
            OpenApiParameter(
                name="location",
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description="Hospital or blood-bank location.",
            ),
        ],
        responses={
            200: inline_serializer(
                name="BloodAvailabilityResponse",
                fields={
                    "blood_group": serializers.CharField(),
                    "location": serializers.CharField(),
                    "available_units": serializers.IntegerField(),
                    "status": serializers.CharField(),
                },
            ),
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        },
        description=(
            "Check available blood stock for a specified blood group "
            "and location. Only hospital users can access this endpoint."
        ),
    )
    def get(self, request):
        blood_group = request.query_params.get(
            "blood_group", ""
        ).strip().upper()

        location = request.query_params.get(
            "location", ""
        ).strip()

        valid_groups = BloodStock.BloodGroup.values

        if not blood_group or not location:
            return Response(
                {
                    "detail": (
                        "Both blood_group and location are required."
                    )
                },
                status=400,
            )

        if blood_group not in valid_groups:
            return Response(
                {"detail": "Invalid blood group."},
                status=400,
            )

        today = timezone.localdate()

        matching_stock = BloodStock.objects.filter(
            blood_group=blood_group,
            location__iexact=location,
            status=BloodStock.StockStatus.AVAILABLE,
            expiry_date__gte=today,
        )

        total_units = (
            matching_stock.aggregate(
                total=Sum("available_units")
            )["total"]
            or 0
        )

        if total_units == 0:
            return Response(
                {
                    "detail": (
                        "No available blood stock found for this "
                        "blood group and location."
                    )
                },
                status=404,
            )

        return Response(
            {
                "blood_group": blood_group,
                "location": location,
                "available_units": total_units,
                "status": "available",
            },
            status=200,
        )


class BloodUnitListCreateView(generics.ListCreateAPIView):
    queryset = BloodUnit.objects.all()
    serializer_class = BloodUnitSerializer
    permission_classes = [IsStaffOrAdmin]

    FILTER_FIELDS = {
        "blood_group": "blood_group",
        "location": "bank_location",
        "expiry_date": "expiry_date",
        "collection_date": "collection_date",
    }

    SORT_FIELDS = {
        "blood_group": "blood_group",
        "location": "bank_location",
        "expiry_date": "expiry_date",
        "collection_date": "collection_date",
    }

    def get_queryset(self):
        queryset = BloodUnit.objects.all()

        # Optionally return only units that are not expired
        # and have a positive quantity.
        if self.request.query_params.get("available", "").lower() == "true":
            queryset = queryset.filter(
                expiry_date__gte=timezone.localdate(),
                quantity__gt=0,
            )

        # Apply supported filters.
        for parameter, model_field in self.FILTER_FIELDS.items():
            value = self.request.query_params.get(parameter)

            if value:
                if parameter in {"blood_group", "location"}:
                    queryset = queryset.filter(
                        **{f"{model_field}__iexact": value}
                    )
                else:
                    queryset = queryset.filter(
                        **{model_field: value}
                    )

        # Apply supported sorting.
        sort_by = self.request.query_params.get("sort_by")
        sort_order = self.request.query_params.get(
            "sort_order", "asc"
        ).lower()

        if sort_by in self.SORT_FIELDS and sort_order in {"asc", "desc"}:
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

    @extend_schema(
        responses={
            200: inline_serializer(
                name="StockSummaryItem",
                many=True,
                fields={
                    "blood_group": serializers.CharField(),
                    "bank_location": serializers.CharField(),
                    "total_quantity": serializers.IntegerField(),
                },
            ),
        },
        description=(
            "Retrieve available, non-expired blood-stock totals "
            "grouped by blood group and blood-bank location. "
            "Only staff and administrators can access this endpoint."
        ),
    )
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
