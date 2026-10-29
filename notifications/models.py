from django.conf import settings
from django.db import models


class LowStockThreshold(models.Model):
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
        unique=True,
    )
    minimum_quantity = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.blood_group}: minimum {self.minimum_quantity}"


class AdminNotification(models.Model):
    blood_group = models.CharField(max_length=3)
    message = models.CharField(max_length=255)
    available_quantity = models.PositiveIntegerField(default=0)
    minimum_quantity = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.blood_group}: {self.message}"


class NotificationDeliveryLog(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "EMAIL", "Email"
        SMS = "SMS", "SMS"

    class Status(models.TextChoices):
        SENT = "SENT", "Sent"
        FAILED = "FAILED", "Failed"

    class NotificationType(models.TextChoices):
        ELIGIBILITY = "ELIGIBILITY", "Eligibility"
        CAMP = "CAMP", "Camp announcement"
        URGENT_NEED = "URGENT_NEED", "Urgent blood need"
        REQUEST_STATUS = "REQUEST_STATUS", "Request status"
        EMERGENCY = "EMERGENCY", "Emergency broadcast"

    recipient = models.CharField(max_length=254)
    channel = models.CharField(max_length=5, choices=Channel.choices)
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
    )
    status = models.CharField(max_length=6, choices=Status.choices)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.channel} {self.status} to {self.recipient} "
            f"({self.notification_type})"
        )