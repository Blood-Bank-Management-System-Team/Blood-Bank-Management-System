from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Max
from django.utils import timezone


def not_in_future(value):
    if value > timezone.localdate():
        raise ValidationError("Date cannot be in the future.")


class DonorProfile(models.Model):
    class BloodGroup(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"

    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"
        OTHER = "OTHER", "Other"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="donor_profile",
        limit_choices_to={"role": "DONOR"},
    )
    blood_group = models.CharField(max_length=3, choices=BloodGroup.choices)
    date_of_birth = models.DateField(validators=[not_in_future])
    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        validators=[MinValueValidator(30), MaxValueValidator(250)],
    )
    gender = models.CharField(max_length=10, choices=Gender.choices)
    address = models.TextField()
    city = models.CharField(max_length=100)
    last_donation_date = models.DateField(null=True, blank=True, validators=[not_in_future])

    has_chronic_illness = models.BooleanField(default=False)
    on_medication = models.BooleanField(default=False)
    recent_surgery_or_tattoo_6_months = models.BooleanField(default=False)
    recent_illness_or_fever_2_weeks = models.BooleanField(default=False)
    is_pregnant_or_breastfeeding = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} ({self.blood_group})"

    def clean(self):
        if self.user_id and self.user.role != "DONOR":
            raise ValidationError("A donor profile can only belong to a user with the DONOR role.")

    def eligibility(self):
        from .services import check_eligibility

        return check_eligibility(self)


class DonationRecord(models.Model):
    donor = models.ForeignKey(DonorProfile, on_delete=models.CASCADE, related_name="donations")
    donation_date = models.DateField(validators=[not_in_future])
    blood_bank_location = models.CharField(max_length=200)
    units = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(2)]
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_donations",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-donation_date", "-id"]

    def __str__(self):
        return f"{self.donor} on {self.donation_date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        latest = self.donor.donations.aggregate(latest=Max("donation_date"))["latest"]
        if self.donor.last_donation_date != latest:
            self.donor.last_donation_date = latest
            self.donor.save(update_fields=["last_donation_date", "updated_at"])
