
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import BloodRequest


User = get_user_model()


class BloodRequestAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hospital = User.objects.create_user(
            username="hospital_test",
            password="TestPass123!",
            role="HOSPITAL",
        )
        self.url = "/api/blood-requests/"

    def authenticate_hospital(self):
        self.client.force_authenticate(user=self.hospital)

    def valid_payload(self):
        return {
            "blood_group": "O+",
            "units": 2,
            "location": "Bengaluru",
            "priority": "emergency",
        }

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_hospital_can_submit_emergency_request(self):
        self.authenticate_hospital()

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("request_id", response.data)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(
            BloodRequest.objects.count(),
            1,
        )
        request = BloodRequest.objects.get()
        self.assertEqual(request.requester, self.hospital)

    def test_scheduled_request_requires_required_date(self):
        self.authenticate_hospital()
        payload = self.valid_payload()
        payload["priority"] = "scheduled"

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("required_date", response.data)

    def test_scheduled_request_accepts_future_date(self):
        self.authenticate_hospital()
        payload = self.valid_payload()
        payload["priority"] = "scheduled"
        payload["required_date"] = (
            date.today() + timedelta(days=2)
        ).isoformat()

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")

    def test_scheduled_request_rejects_past_date(self):
        self.authenticate_hospital()
        payload = self.valid_payload()
        payload["priority"] = "scheduled"
        payload["required_date"] = (
            date.today() - timedelta(days=1)
        ).isoformat()

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_zero_units_are_rejected(self):
        self.authenticate_hospital()
        payload = self.valid_payload()
        payload["units"] = 0

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_donor_cannot_submit_request(self):
        donor = User.objects.create_user(
            username="donor_test",
            password="TestPass123!",
            role="DONOR",
        )
        self.client.force_authenticate(user=donor)

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 403)
