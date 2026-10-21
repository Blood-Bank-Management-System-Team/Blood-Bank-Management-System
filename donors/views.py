from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsDonor, IsStaffOrAdmin

from .models import DonorProfile
from .serializers import DonorListSerializer, DonorProfileSerializer, EligibilitySerializer

NO_PROFILE = {"detail": "Donor profile not found. Complete your donor profile first."}


class DonorProfileView(APIView):
    permission_classes = [IsDonor]

    def get_profile(self, request):
        return DonorProfile.objects.filter(user=request.user).first()

    def get(self, request):
        profile = self.get_profile(request)
        if profile is None:
            return Response(NO_PROFILE, status=status.HTTP_404_NOT_FOUND)
        return Response(DonorProfileSerializer(profile).data)

    def post(self, request):
        if self.get_profile(request) is not None:
            return Response(
                {"detail": "Donor profile already exists; use PUT to update it."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = DonorProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request):
        profile = self.get_profile(request)
        if profile is None:
            return Response(NO_PROFILE, status=status.HTTP_404_NOT_FOUND)
        serializer = DonorProfileSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DonorEligibilityView(APIView):
    permission_classes = [IsDonor]

    def get(self, request):
        profile = DonorProfile.objects.filter(user=request.user).first()
        if profile is None:
            return Response(NO_PROFILE, status=status.HTTP_404_NOT_FOUND)
        return Response(EligibilitySerializer(profile.eligibility()).data)


class DonorListView(generics.ListAPIView):
    permission_classes = [IsStaffOrAdmin]
    serializer_class = DonorListSerializer

    def get_queryset(self):
        qs = DonorProfile.objects.select_related("user").order_by("id")
        blood_group = self.request.query_params.get("blood_group")
        if blood_group:
            # an unescaped "+" in a query string arrives as a space (e.g. "O+" -> "O ")
            qs = qs.filter(blood_group=blood_group.replace(" ", "+").strip().upper())
        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(city__iexact=city.strip())
        return qs
