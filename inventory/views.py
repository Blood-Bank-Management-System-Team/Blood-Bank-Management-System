
from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsStaffOrAdmin

from .models import BloodUnit
from .serializers import BloodUnitSerializer


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
