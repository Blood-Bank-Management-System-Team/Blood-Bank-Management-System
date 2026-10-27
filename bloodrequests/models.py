
import uuid

from django.conf import settings
from django.db import models


class BloodRequest(models.Model):
    class BloodGroup(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"

    class Priority(models.TextChoices):
        EMERGENCY = "emergency", "Emergency"
        SCHEDULED = "scheduled", "Scheduled"

    class RequestStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        FULFILLED = "fulfilled", "Fulfilled"
        CANCELLED = "cancelled", "Cancelled"

    request_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="blood_requests",
    )
    blood_group = models.CharField(
        max_length=3,
        choices=BloodGroup.choices,
    )
    units = models.PositiveIntegerField()
    location = models.CharField(max_length=100)
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
    )
    required_date = models.DateField(
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=10,
        choices=RequestStatus.choices,
        default=RequestStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.request_id} - {self.blood_group} ({self.status})"

class BloodReservation(models.Model):
    blood_request = models.ForeignKey(
        BloodRequest,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    blood_stock = models.ForeignKey(
        "inventory.BloodStock",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    units = models.PositiveIntegerField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(units__gt=0),
                name="reservation_units_positive",
            ),
        ]

    def __str__(self):
        return (
            f"Reservation for {self.blood_request.request_id}: "
            f"{self.units} units"
        )