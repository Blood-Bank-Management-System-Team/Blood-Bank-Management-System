from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from inventory.models import BloodStock

User = get_user_model()


class BloodAvailabilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hospital = User.objects.create_user(
            username="hospital1",
            password="TestPass123!",
            role="HOSPITAL",
        )
        self.donor = User.objects.create_user(
            username="donor1",
            password="TestPass123!",
            role="DONOR",
        )
        self.client.force_authenticate(user=self.hospital)

        today = timezone.localdate()

        BloodStock.objects.create(
            blood_group="O+",
            location="Bengaluru",
            available_units=5,
            collection_date=today - timedelta(days=2),
            expiry_date=today + timedelta(days=30),
            status="AVAILABLE",
        )
        BloodStock.objects.create(
            blood_group="O+",
            location="Bengaluru",
            available_units=3,
            collection_date=today - timedelta(days=1),
            expiry_date=today + timedelta(days=20),
            status="AVAILABLE",
        )
        BloodStock.objects.create(
            blood_group="O+",
            location="Bengaluru",
            available_units=10,
            collection_date=today - timedelta(days=5),
            expiry_date=today + timedelta(days=20),
            status="RESERVED",
        )
        BloodStock.objects.create(
            blood_group="O+",
            location="Bengaluru",
            available_units=7,
            collection_date=today - timedelta(days=40),
            expiry_date=today - timedelta(days=1),
            status="AVAILABLE",
        )

    def test_search_sums_available_unexpired_stock(self):
        response = self.client.get(
            "/api/blood/availability/",
            {"blood_group": "O+", "location": "Bengaluru"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["available_units"], 8)

    def test_missing_parameters_rejected(self):
        response = self.client.get("/api/blood/availability/")
        self.assertEqual(response.status_code, 400)

    def test_invalid_blood_group_rejected(self):
        response = self.client.get(
            "/api/blood/availability/",
            {"blood_group": "Z+", "location": "Bengaluru"},
        )
        self.assertEqual(response.status_code, 400)

    def test_donor_cannot_search(self):
        self.client.force_authenticate(user=self.donor)
        response = self.client.get(
            "/api/blood/availability/",
            {"blood_group": "O+", "location": "Bengaluru"},
        )
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_search(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(
            "/api/blood/availability/",
            {"blood_group": "O+", "location": "Bengaluru"},
        )
        self.assertEqual(response.status_code, 401)

    def test_no_matching_stock_returns_not_found(self):
        response = self.client.get(
            "/api/blood/availability/",
            {"blood_group": "A+", "location": "Bengaluru"},
        )
        self.assertEqual(response.status_code, 404)
