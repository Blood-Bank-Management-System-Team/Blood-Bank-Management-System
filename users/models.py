from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        DONOR = "DONOR", "Donor"
        STAFF = "STAFF", "Blood Bank Staff"
        HOSPITAL = "HOSPITAL", "Hospital/Patient"
        ADMIN = "ADMIN", "Administrator"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.DONOR)
    phone = models.CharField(max_length=20, blank=True)
