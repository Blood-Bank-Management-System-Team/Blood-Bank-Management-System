from django.shortcuts import render

# Create your views here.

from rest_framework import generics

from users.permissions import IsStaffOrAdmin

from .models import BloodUnit
from .serializers import BloodUnitSerializer


class BloodUnitListCreateView(generics.ListCreateAPIView):
    queryset = BloodUnit.objects.all().order_by("id")
    serializer_class = BloodUnitSerializer
    permission_classes = [IsStaffOrAdmin]

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
