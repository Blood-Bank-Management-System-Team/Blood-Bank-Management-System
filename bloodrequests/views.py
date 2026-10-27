from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsHospital, IsStaffOrAdmin
from inventory.models import BloodStock

from .models import BloodRequest, BloodReservation
from .serializers import BloodRequestSerializer


# Red blood cell compatibility:
# The dictionary maps a recipient's blood group to compatible donor groups.
RBC_COMPATIBILITY = {
    "O-": ["O-"],
    "O+": ["O-", "O+"],
    "A-": ["O-", "A-"],
    "A+": ["O-", "O+", "A-", "A+"],
    "B-": ["O-", "B-"],
    "B+": ["O-", "O+", "B-", "B+"],
    "AB-": ["O-", "A-", "B-", "AB-"],
    "AB+": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
}


class BloodRequestCreateView(generics.CreateAPIView):
    queryset = BloodRequest.objects.all()
    serializer_class = BloodRequestSerializer
    permission_classes = [IsHospital]

    def perform_create(self, serializer):
        serializer.save(requester=self.request.user)


class BloodRequestListView(generics.ListAPIView):
    """Hospitals see their own requests; staff/admin can see all requests."""

    serializer_class = BloodRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        role = str(getattr(user, "role", "")).lower()

        if role in {"staff", "admin"} or user.is_superuser:
            return BloodRequest.objects.all().order_by("-created_at")

        if role == "hospital":
            return BloodRequest.objects.filter(
                requester=user
            ).order_by("-created_at")

        return BloodRequest.objects.none()


class BloodRequestProcessView(APIView):
    """Staff/admin approve, reject, or fulfil requests."""

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

            # APPROVE: reserve compatible stock.
            if new_status == BloodRequest.RequestStatus.APPROVED:
                if blood_request.status != BloodRequest.RequestStatus.PENDING:
                    return Response(
                        {"detail": "Only pending requests can be approved."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                compatible_groups = RBC_COMPATIBILITY.get(
                    blood_request.blood_group, []
                )

                if not compatible_groups:
                    return Response(
                        {"detail": "Unsupported recipient blood group."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                today = timezone.localdate()

                stock_rows = list(
                    BloodStock.objects.select_for_update()
                    .filter(
                        blood_group__in=compatible_groups,
                        location__iexact=blood_request.location,
                        status=BloodStock.StockStatus.AVAILABLE,
                        expiry_date__gte=today,
                        available_units__gt=0,
                    )
                    .order_by("expiry_date", "pk")
                )

                total_available = sum(
                    stock.available_units for stock in stock_rows
                )

                if total_available < blood_request.units:
                    return Response(
                        {
                            "detail": (
                                "Insufficient compatible blood stock "
                                "to approve this request."
                            ),
                            "required_units": blood_request.units,
                            "available_units": total_available,
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                remaining = blood_request.units

                for stock in stock_rows:
                    if remaining == 0:
                        break

                    reserved_units = min(
                        stock.available_units,
                        remaining,
                    )

                    BloodReservation.objects.create(
                        blood_request=blood_request,
                        blood_stock=stock,
                        units=reserved_units,
                    )

                    stock.available_units -= reserved_units

                    update_fields = ["available_units", "updated_at"]

                    if stock.available_units == 0:
                        stock.status = BloodStock.StockStatus.RESERVED
                        update_fields.append("status")

                    stock.save(update_fields=update_fields)
                    remaining -= reserved_units

            # REJECT: only pending requests can be rejected.
            elif new_status == BloodRequest.RequestStatus.REJECTED:
                if blood_request.status != BloodRequest.RequestStatus.PENDING:
                    return Response(
                        {"detail": "Only pending requests can be rejected."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # FULFIL: consume the existing reservation, not stock again.
            elif new_status == BloodRequest.RequestStatus.FULFILLED:
                if blood_request.status != BloodRequest.RequestStatus.APPROVED:
                    return Response(
                        {
                            "detail": (
                                "Only approved requests can be fulfilled."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                reservations = list(
                    BloodReservation.objects.select_for_update().filter(
                        blood_request=blood_request,
                        active=True,
                    )
                )

                reserved_total = sum(
                    reservation.units for reservation in reservations
                )

                if reserved_total != blood_request.units:
                    return Response(
                        {
                            "detail": (
                                "The request does not have a complete "
                                "active reservation."
                            )
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                now = timezone.now()

                for reservation in reservations:
                    reservation.active = False
                    reservation.consumed_at = now
                    reservation.save(
                        update_fields=["active", "consumed_at"]
                    )

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


class BloodRequestCancelView(APIView):
    """Allow the request owner or staff/admin to cancel an approved request."""

    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        user = request.user
        role = str(getattr(user, "role", "")).lower()
        is_staff_or_admin = role in {"staff", "admin"} or user.is_superuser

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

            if blood_request.requester_id != user.pk and not is_staff_or_admin:
                return Response(
                    {"detail": "You cannot cancel this request."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            if blood_request.status != BloodRequest.RequestStatus.APPROVED:
                return Response(
                    {"detail": "Only approved requests can be cancelled."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            reservations = list(
                BloodReservation.objects.select_for_update().filter(
                    blood_request=blood_request,
                    active=True,
                )
            )

            if sum(r.units for r in reservations) != blood_request.units:
                return Response(
                    {
                        "detail": (
                            "The request does not have a complete active "
                            "reservation; stock was not released."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            now = timezone.now()

            for reservation in reservations:
                stock = BloodStock.objects.select_for_update().get(
                    pk=reservation.blood_stock_id
                )

                stock.available_units += reservation.units

                update_fields = ["available_units", "updated_at"]

                # A previously empty row becomes available again.
                if stock.status == BloodStock.StockStatus.RESERVED:
                    stock.status = BloodStock.StockStatus.AVAILABLE
                    update_fields.append("status")

                stock.save(update_fields=update_fields)

                reservation.active = False
                reservation.released_at = now
                reservation.save(
                    update_fields=["active", "released_at"]
                )

            blood_request.status = BloodRequest.RequestStatus.CANCELLED
            blood_request.save(update_fields=["status"])

        return Response(
            {
                "request_id": str(blood_request.request_id),
                "status": blood_request.status,
                "detail": "Request cancelled and reserved stock released.",
            },
            status=status.HTTP_200_OK,
        )