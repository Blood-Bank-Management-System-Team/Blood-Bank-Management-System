
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
