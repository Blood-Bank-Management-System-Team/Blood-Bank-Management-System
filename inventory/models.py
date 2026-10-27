
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone



class BloodStock(models.Model):
    class BloodGroup(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"

    class StockStatus(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        RESERVED = "RESERVED", "Reserved"
        DISPOSED = "DISPOSED", "Disposed"

    blood_group = models.CharField(
        max_length=3,
        choices=BloodGroup.choices,
    )
    location = models.CharField(max_length=100)
    available_units = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
    )
    collection_date = models.DateField()
    expiry_date = models.DateField()
    status = models.CharField(
        max_length=10,
        choices=StockStatus.choices,
        default=StockStatus.AVAILABLE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["blood_group", "location"]
        indexes = [
            models.Index(
                fields=["blood_group", "location", "status"],
                name="stock_search_idx",
            ),
        ]

    def clean(self):
        super().clean()

        if self.collection_date and self.expiry_date:
            if self.expiry_date <= self.collection_date:
                raise ValidationError({
                    "expiry_date": (
                        "Expiry date must be after the collection date."
                    )
                })

    def __str__(self):
        return (
            f"{self.blood_group} - {self.location} "
            f"({self.available_units} units)"
        )

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

