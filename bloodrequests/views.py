
from rest_framework import generics

from users.permissions import IsHospital

from .models import BloodRequest
from .serializers import BloodRequestSerializer


class BloodRequestCreateView(generics.CreateAPIView):
    queryset = BloodRequest.objects.all()
    serializer_class = BloodRequestSerializer
    permission_classes = [IsHospital]

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)
