
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class DonationCamp(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    date = models.DateField()
    venue = models.CharField(max_length=250)
    available_slots = models.PositiveIntegerField(
        validators=[MinValueValidator(1)]
    )
    is_published = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_donation_camps",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date", "name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(available_slots__gte=1),
                name="camp_available_slots_at_least_one",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.date}"

    @property
    def registered_count(self):
        return self.registrations.count()

    @property
    def remaining_slots(self):
        return max(0, self.available_slots - self.registered_count)

    @property
    def is_full(self):
        return self.registered_count >= self.available_slots


class CampRegistration(models.Model):
    camp = models.ForeignKey(
        DonationCamp,
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    donor = models.ForeignKey(
        "donors.DonorProfile",
        on_delete=models.CASCADE,
        related_name="camp_registrations",
    )
    registered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-registered_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["camp", "donor"],
                name="unique_donor_registration_per_camp",
            ),
        ]

    def __str__(self):
        return f"{self.donor} - {self.camp}"