
from django.db import models
from django.utils import timezone


class BloodUnit(models.Model):
    BLOOD_GROUPS = [
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
    ]

    blood_group = models.CharField(
        max_length=3,
        choices=BLOOD_GROUPS,
    )
    quantity = models.PositiveIntegerField()
    collection_date = models.DateField()
    expiry_date = models.DateField()
    bank_location = models.CharField(max_length=200)

    created_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="blood_units_created",
        null=True,
        blank=True,
    )
    updated_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        related_name="blood_units_updated",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_expired(self):
        return self.expiry_date < timezone.localdate()

    @property
    def is_available(self):
        return not self.is_expired and self.quantity > 0

    def __str__(self):
        return f"{self.blood_group} - Unit {self.id}"
