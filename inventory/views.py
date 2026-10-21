
from django.utils import timezone
from rest_framework import generics

from users.permissions import IsStaffOrAdmin

from .models import BloodUnit
from .serializers import BloodUnitSerializer


class BloodUnitListCreateView(generics.ListCreateAPIView):
    serializer_class = BloodUnitSerializer
    permission_classes = [IsStaffOrAdmin]

    def get_queryset(self):
        queryset = BloodUnit.objects.all().order_by("id")

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
