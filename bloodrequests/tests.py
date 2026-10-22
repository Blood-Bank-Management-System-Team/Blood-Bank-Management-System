
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from inventory.models import BloodStock
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
        self.staff = User.objects.create_user(
            username="staff_test",
            password="TestPass123!",
            role="STAFF",
        )
        self.donor = User.objects.create_user(
            username="donor_test",
            password="TestPass123!",
            role="DONOR",
        )

        self.url = "/api/blood-requests/"

    def authenticate_hospital(self):
        self.client.force_authenticate(user=self.hospital)

    def authenticate_staff(self):
        self.client.force_authenticate(user=self.staff)

    def valid_payload(self):
        return {
            "blood_group": "O+",
            "units": 2,
            "location": "Bengaluru",
            "priority": "emergency",
        }

    def create_request(self, **overrides):
        data = {
            "requester": self.hospital,
            "blood_group": "O+",
            "units": 2,
            "location": "Bengaluru",
            "priority": "emergency",
            "status": BloodRequest.RequestStatus.PENDING,
        }
        data.update(overrides)
        return BloodRequest.objects.create(**data)

    def process_url(self, blood_request):
        return f"{self.url}{blood_request.request_id}/process/"

    def process_request(self, blood_request, new_status):
        return self.client.post(
            self.process_url(blood_request),
            {"status": new_status},
            format="json",
        )

    def create_stock(self, units, **overrides):
        today = timezone.localdate()
        data = {
            "blood_group": "O+",
            "location": "Bengaluru",
            "available_units": units,
            "collection_date": today - timedelta(days=1),
            "expiry_date": today + timedelta(days=10),
            "status": BloodStock.StockStatus.AVAILABLE,
        }
        data.update(overrides)
        return BloodStock.objects.create(**data)

    # BB-11 submission tests

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
        self.assertEqual(BloodRequest.objects.count(), 1)

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
        self.client.force_authenticate(user=self.donor)

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    # BB-12 request processing tests

    def test_staff_can_approve_pending_request(self):
        self.authenticate_staff()
        blood_request = self.create_request()

        response = self.process_request(blood_request, "approved")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "approved")

        blood_request.refresh_from_db()
        self.assertEqual(blood_request.status, "approved")

    def test_staff_can_reject_pending_request(self):
        self.authenticate_staff()
        blood_request = self.create_request()

        response = self.process_request(blood_request, "rejected")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "rejected")

        blood_request.refresh_from_db()
        self.assertEqual(blood_request.status, "rejected")

    def test_fulfilment_deducts_stock_across_records(self):
        self.authenticate_staff()
        blood_request = self.create_request(units=5)

        first_stock = self.create_stock(2)
        second_stock = self.create_stock(4)

        response = self.process_request(blood_request, "fulfilled")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "fulfilled")

        first_stock.refresh_from_db()
        second_stock.refresh_from_db()
        blood_request.refresh_from_db()

        self.assertEqual(first_stock.available_units, 0)
        self.assertEqual(second_stock.available_units, 1)
        self.assertEqual(blood_request.status, "fulfilled")

    def test_insufficient_stock_does_not_change_stock_or_request(self):
        self.authenticate_staff()
        blood_request = self.create_request(units=5)
        stock = self.create_stock(3)

        response = self.process_request(blood_request, "fulfilled")

        self.assertEqual(response.status_code, 409)

        stock.refresh_from_db()
        blood_request.refresh_from_db()

        self.assertEqual(stock.available_units, 3)
        self.assertEqual(blood_request.status, "pending")

    def test_expired_stock_is_not_used(self):
        self.authenticate_staff()
        blood_request = self.create_request(units=2)
        stock = self.create_stock(
            5,
            expiry_date=timezone.localdate() - timedelta(days=1),
        )

        response = self.process_request(blood_request, "fulfilled")

        self.assertEqual(response.status_code, 409)

        stock.refresh_from_db()
        blood_request.refresh_from_db()

        self.assertEqual(stock.available_units, 5)
        self.assertEqual(blood_request.status, "pending")

    def test_stock_from_another_location_is_not_used(self):
        self.authenticate_staff()
        blood_request = self.create_request(units=2)
        stock = self.create_stock(5, location="Mysuru")

        response = self.process_request(blood_request, "fulfilled")

        self.assertEqual(response.status_code, 409)

        stock.refresh_from_db()
        self.assertEqual(stock.available_units, 5)

    def test_hospital_cannot_process_request(self):
        self.client.force_authenticate(user=self.hospital)
        blood_request = self.create_request()

        response = self.process_request(blood_request, "approved")

        self.assertEqual(response.status_code, 403)

        blood_request.refresh_from_db()
        self.assertEqual(blood_request.status, "pending")

    def test_donor_cannot_process_request(self):
        self.client.force_authenticate(user=self.donor)
        blood_request = self.create_request()

        response = self.process_request(blood_request, "approved")

        self.assertEqual(response.status_code, 403)

        blood_request.refresh_from_db()
        self.assertEqual(blood_request.status, "pending")

    def test_unauthenticated_user_cannot_process_request(self):
        blood_request = self.create_request()

        response = self.process_request(blood_request, "approved")

        self.assertEqual(response.status_code, 401)

    def test_invalid_status_is_rejected(self):
        self.authenticate_staff()
        blood_request = self.create_request()

        response = self.process_request(blood_request, "cancelled")

        self.assertEqual(response.status_code, 400)

        blood_request.refresh_from_db()
        self.assertEqual(blood_request.status, "pending")

    def test_already_processed_request_cannot_be_processed_again(self):
        self.authenticate_staff()
        blood_request = self.create_request(
            status=BloodRequest.RequestStatus.APPROVED,
        )

        response = self.process_request(blood_request, "rejected")

        self.assertEqual(response.status_code, 400)

        blood_request.refresh_from_db()
        self.assertEqual(blood_request.status, "approved")

    def test_nonexistent_request_returns_404(self):
        import uuid

        self.authenticate_staff()

        response = self.client.post(
            f"{self.url}{uuid.uuid4()}/process/",
            {"status": "approved"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
