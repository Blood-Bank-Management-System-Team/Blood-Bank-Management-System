from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from inventory.models import BloodStock
from bloodrequests.models import BloodRequest, BloodReservation


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

    def cancel_url(self, blood_request):
        return f"{self.url}{blood_request.request_id}/cancel/"

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

    def approve_request(self, blood_request):
        return self.process_request(blood_request, "approved")

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

        blood_request = BloodRequest.objects.get()
        self.assertEqual(blood_request.requester, self.hospital)

    def test_scheduled_request_requires_required_date(self):
        self.authenticate_hospital()
        payload = self.valid_payload()
        payload["priority"] = "scheduled"

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("required_date", response.data)

    def test_scheduled_request_accepts_future_date(self):
        self.authenticate_hospital()
        payload = self.valid_payload()
        payload["priority"] = "scheduled"
        payload["required_date"] = (
            date.today() + timedelta(days=2)
        ).isoformat()

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending")

    def test_scheduled_request_rejects_past_date(self):
        self.authenticate_hospital()
        payload = self.valid_payload()
        payload["priority"] = "scheduled"
        payload["required_date"] = (
            date.today() - timedelta(days=1)
        ).isoformat()

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)

    def test_zero_units_are_rejected(self):
        self.authenticate_hospital()
        payload = self.valid_payload()
        payload["units"] = 0

        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)

    def test_donor_cannot_submit_request(self):
        self.client.force_authenticate(user=self.donor)

        response = self.client.post(
            self.url,
            self.valid_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    # BB-12 / BB-25 processing tests

    def test_staff_can_approve_and_reserve_stock(self):
        self.authenticate_staff()
        blood_request = self.create_request()
        stock = self.create_stock(5)

        response = self.approve_request(blood_request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "approved")

        stock.refresh_from_db()
        blood_request.refresh_from_db()

        self.assertEqual(stock.available_units, 3)
        self.assertEqual(blood_request.status, "approved")
        self.assertEqual(
            BloodReservation.objects.filter(
                blood_request=blood_request,
                active=True,
            ).count(),
            1,
        )

    def test_staff_can_reject_pending_request(self):
        self.authenticate_staff()
        blood_request = self.create_request()
        stock = self.create_stock(5)

        response = self.process_request(blood_request, "rejected")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "rejected")

        blood_request.refresh_from_db()
        stock.refresh_from_db()

        self.assertEqual(blood_request.status, "rejected")
        self.assertEqual(stock.available_units, 5)
        self.assertEqual(BloodReservation.objects.count(), 0)

    def test_approval_reserves_stock_across_records(self):
        self.authenticate_staff()
        blood_request = self.create_request(units=5)

        first_stock = self.create_stock(2)
        second_stock = self.create_stock(4)

        response = self.approve_request(blood_request)

        self.assertEqual(response.status_code, 200)

        first_stock.refresh_from_db()
        second_stock.refresh_from_db()

        self.assertEqual(first_stock.available_units, 0)
        self.assertEqual(second_stock.available_units, 1)

        self.assertEqual(
            sum(
                reservation.units
                for reservation in BloodReservation.objects.filter(
                    blood_request=blood_request,
                    active=True,
                )
            ),
            5,
        )

    def test_fulfilment_consumes_reservation_without_second_deduction(self):
        self.authenticate_staff()
        blood_request = self.create_request(units=5)

        first_stock = self.create_stock(2)
        second_stock = self.create_stock(4)

        approval = self.approve_request(blood_request)
        self.assertEqual(approval.status_code, 200)

        first_stock.refresh_from_db()
        second_stock.refresh_from_db()

        reserved_first = first_stock.available_units
        reserved_second = second_stock.available_units

        response = self.process_request(blood_request, "fulfilled")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "fulfilled")

        first_stock.refresh_from_db()
        second_stock.refresh_from_db()
        blood_request.refresh_from_db()

        self.assertEqual(first_stock.available_units, reserved_first)
        self.assertEqual(second_stock.available_units, reserved_second)
        self.assertEqual(blood_request.status, "fulfilled")

        reservations = BloodReservation.objects.filter(
            blood_request=blood_request
        )
        self.assertFalse(reservations.filter(active=True).exists())
        self.assertTrue(
            reservations.filter(consumed_at__isnull=False).exists()
        )

    def test_insufficient_stock_does_not_partially_reserve(self):
        self.authenticate_staff()
        blood_request = self.create_request(units=5)
        stock = self.create_stock(3)

        response = self.approve_request(blood_request)

        self.assertEqual(response.status_code, 409)

        stock.refresh_from_db()
        blood_request.refresh_from_db()

        self.assertEqual(stock.available_units, 3)
        self.assertEqual(blood_request.status, "pending")
        self.assertFalse(
            BloodReservation.objects.filter(
                blood_request=blood_request
            ).exists()
        )

    def test_expired_stock_is_not_reserved(self):
        self.authenticate_staff()
        blood_request = self.create_request(units=2)
        stock = self.create_stock(
            5,
            expiry_date=timezone.localdate() - timedelta(days=1),
        )

        response = self.approve_request(blood_request)

        self.assertEqual(response.status_code, 409)

        stock.refresh_from_db()
        blood_request.refresh_from_db()

        self.assertEqual(stock.available_units, 5)
        self.assertEqual(blood_request.status, "pending")

    def test_stock_from_another_location_is_not_reserved(self):
        self.authenticate_staff()
        blood_request = self.create_request(units=2)
        stock = self.create_stock(5, location="Mysuru")

        response = self.approve_request(blood_request)

        self.assertEqual(response.status_code, 409)

        stock.refresh_from_db()
        self.assertEqual(stock.available_units, 5)

    def test_compatible_o_negative_stock_can_be_reserved_for_o_positive(self):
        self.authenticate_staff()
        blood_request = self.create_request(
            blood_group="O+",
            units=2,
        )
        stock = self.create_stock(3, blood_group="O-")

        response = self.approve_request(blood_request)

        self.assertEqual(response.status_code, 200)

        stock.refresh_from_db()
        self.assertEqual(stock.available_units, 1)

    def test_incompatible_stock_is_not_reserved(self):
        self.authenticate_staff()
        blood_request = self.create_request(
            blood_group="O+",
            units=2,
        )
        stock = self.create_stock(5, blood_group="A+")

        response = self.approve_request(blood_request)

        self.assertEqual(response.status_code, 409)

        stock.refresh_from_db()
        self.assertEqual(stock.available_units, 5)

    def test_hospital_can_cancel_own_approved_request_and_release_stock(self):
        self.authenticate_staff()
        blood_request = self.create_request()
        stock = self.create_stock(5)

        approval = self.approve_request(blood_request)
        self.assertEqual(approval.status_code, 200)

        stock.refresh_from_db()
        self.assertEqual(stock.available_units, 3)

        self.client.force_authenticate(user=self.hospital)
        response = self.client.post(self.cancel_url(blood_request))

        self.assertEqual(response.status_code, 200)

        stock.refresh_from_db()
        blood_request.refresh_from_db()

        self.assertEqual(stock.available_units, 5)
        self.assertEqual(blood_request.status, "cancelled")
        self.assertFalse(
            BloodReservation.objects.filter(
                blood_request=blood_request,
                active=True,
            ).exists()
        )
        self.assertTrue(
            BloodReservation.objects.filter(
                blood_request=blood_request,
                released_at__isnull=False,
            ).exists()
        )

    def test_cancelled_request_cannot_be_cancelled_again(self):
        self.authenticate_staff()
        blood_request = self.create_request()
        self.create_stock(5)
        self.approve_request(blood_request)

        self.client.force_authenticate(user=self.hospital)
        first_response = self.client.post(self.cancel_url(blood_request))
        second_response = self.client.post(self.cancel_url(blood_request))

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 400)

    def test_hospital_cannot_cancel_another_hospitals_request(self):
        self.authenticate_staff()
        blood_request = self.create_request()
        self.create_stock(5)
        self.approve_request(blood_request)

        other_hospital = User.objects.create_user(
            username="other_hospital",
            password="TestPass123!",
            role="HOSPITAL",
        )
        self.client.force_authenticate(user=other_hospital)

        response = self.client.post(self.cancel_url(blood_request))

        self.assertEqual(response.status_code, 403)

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