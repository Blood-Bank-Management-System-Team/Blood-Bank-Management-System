from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from inventory.compatibility import is_blood_compatible
from inventory.models import BloodStock, BloodUnit


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


class BloodUnitAPITests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="test_staff",
            password="TestStaff@12345",
            role=User.Role.STAFF,
        )
        self.donor = User.objects.create_user(
            username="test_donor",
            password="TestDonor@12345",
            role=User.Role.DONOR,
        )

        self.list_url = "/api/inventory/"
        self.stock_summary_url = "/api/inventory/stock-summary/"

        self.unit = BloodUnit.objects.create(
            blood_group="O+",
            quantity=2,
            collection_date="2026-10-01",
            expiry_date="2026-11-25",
            bank_location="Test Blood Bank",
            created_by=self.staff,
            updated_by=self.staff,
        )
        self.detail_url = f"/api/inventory/{self.unit.id}/"

    def test_staff_can_view_blood_units(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

    def test_donor_cannot_view_blood_units(self):
        self.client.force_authenticate(user=self.donor)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_staff_can_create_blood_unit(self):
        self.client.force_authenticate(user=self.staff)
        data = {
            "blood_group": "A+",
            "quantity": 3,
            "collection_date": "2026-10-01",
            "expiry_date": "2026-11-25",
            "bank_location": "Test Blood Bank",
        }
        response = self.client.post(
            self.list_url,
            data,
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            BloodUnit.objects.get(id=response.data["id"]).created_by,
            self.staff,
        )

    def test_staff_can_update_blood_unit(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.patch(
            self.detail_url,
            {"quantity": 5},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.quantity, 5)
        self.assertEqual(self.unit.updated_by, self.staff)

    def test_staff_can_delete_blood_unit(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            BloodUnit.objects.filter(id=self.unit.id).exists()
        )

    def test_stock_summary_groups_by_blood_group_and_location(self):
        BloodUnit.objects.create(
            blood_group="O+",
            quantity=3,
            collection_date="2026-10-01",
            expiry_date="2026-11-25",
            bank_location="Test Blood Bank",
            created_by=self.staff,
            updated_by=self.staff,
        )
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.stock_summary_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["blood_group"], "O+")
        self.assertEqual(
            response.data[0]["bank_location"],
            "Test Blood Bank",
        )
        self.assertEqual(response.data[0]["total_quantity"], 5)

    def test_stock_summary_excludes_expired_units(self):
        self.unit.expiry_date = "2026-10-20"
        self.unit.save()

        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.stock_summary_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_expired_unit_is_flagged(self):
        self.unit.expiry_date = "2026-10-20"
        self.unit.save()

        self.client.force_authenticate(user=self.staff)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data[0]["is_expired"])

    def test_available_filter_excludes_expired_units(self):
        self.unit.expiry_date = "2026-10-20"
        self.unit.save()

        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            self.list_url,
            {"available": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_available_filter_includes_non_expired_units(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            self.list_url,
            {"available": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertFalse(response.data[0]["is_expired"])

    def test_available_filter_excludes_zero_quantity_units(self):
        self.unit.quantity = 0
        self.unit.save()

        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            self.list_url,
            {"available": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)


class BloodCompatibilityTests(TestCase):
    def test_o_negative_is_compatible_with_all_groups(self):
        recipients = [
            "O-",
            "O+",
            "A-",
            "A+",
            "B-",
            "B+",
            "AB-",
            "AB+",
        ]

        for recipient in recipients:
            with self.subTest(recipient=recipient):
                self.assertTrue(
                    is_blood_compatible("O-", recipient)
                )

    def test_o_positive_compatibility(self):
        self.assertTrue(is_blood_compatible("O+", "O+"))
        self.assertTrue(is_blood_compatible("O+", "A+"))
        self.assertTrue(is_blood_compatible("O+", "B+"))
        self.assertTrue(is_blood_compatible("O+", "AB+"))

        self.assertFalse(is_blood_compatible("O+", "A-"))
        self.assertFalse(is_blood_compatible("O+", "O-"))

    def test_a_positive_compatibility(self):
        self.assertTrue(is_blood_compatible("A+", "A+"))
        self.assertTrue(is_blood_compatible("A+", "AB+"))
        self.assertFalse(is_blood_compatible("A+", "B+"))
        self.assertFalse(is_blood_compatible("A+", "A-"))

    def test_b_positive_compatibility(self):
        self.assertTrue(is_blood_compatible("B+", "B+"))
        self.assertTrue(is_blood_compatible("B+", "AB+"))
        self.assertFalse(is_blood_compatible("B+", "A+"))

    def test_ab_positive_only_accepts_ab_positive(self):
        self.assertTrue(is_blood_compatible("AB+", "AB+"))
        self.assertFalse(is_blood_compatible("AB+", "O+"))
        self.assertFalse(is_blood_compatible("AB+", "A+"))

    def test_invalid_blood_group_is_incompatible(self):
        self.assertFalse(is_blood_compatible("INVALID", "O+"))
        self.assertFalse(is_blood_compatible("O+", "INVALID"))


class CrossBankSearchTests(TestCase):
    def setUp(self):
        from datetime import timedelta

        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        self.client = APIClient()
        User = get_user_model()

        self.hospital = User.objects.create_user(
            username="cross_bank_hospital",
            password="TestPass123!",
            role="HOSPITAL",
        )
        self.client.force_authenticate(user=self.hospital)

        self.url = "/api/inventory/cross-bank-search/"
        today = timezone.localdate()

        BloodStock.objects.create(
            blood_group="O-",
            location="Bengaluru",
            available_units=3,
            collection_date=today - timedelta(days=1),
            expiry_date=today + timedelta(days=10),
            status=BloodStock.StockStatus.AVAILABLE,
        )
        BloodStock.objects.create(
            blood_group="O+",
            location="Mysuru",
            available_units=5,
            collection_date=today - timedelta(days=1),
            expiry_date=today + timedelta(days=5),
            status=BloodStock.StockStatus.AVAILABLE,
        )
        BloodStock.objects.create(
            blood_group="A+",
            location="Bengaluru",
            available_units=8,
            collection_date=today - timedelta(days=1),
            expiry_date=today + timedelta(days=10),
            status=BloodStock.StockStatus.AVAILABLE,
        )
        BloodStock.objects.create(
            blood_group="O-",
            location="Mandya",
            available_units=7,
            collection_date=today - timedelta(days=20),
            expiry_date=today - timedelta(days=1),
            status=BloodStock.StockStatus.AVAILABLE,
        )

    def test_search_returns_compatible_stock_across_locations(self):
        response = self.client.get(
            self.url,
            {"blood_group": "O+", "location": "Bengaluru"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_units"], 8)

        locations = {
            item["location"] for item in response.data["results"]
        }
        self.assertEqual(locations, {"Bengaluru", "Mysuru"})

    def test_requested_location_is_prioritised(self):
        response = self.client.get(
            self.url,
            {"blood_group": "O+", "location": "Bengaluru"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["results"][0]["is_requested_location"])

    def test_incompatible_and_expired_stock_are_excluded(self):
        response = self.client.get(
            self.url,
            {"blood_group": "O+", "location": "Bengaluru"},
        )

        self.assertEqual(response.status_code, 200)

        groups = {
            item["blood_group"] for item in response.data["results"]
        }
        locations = {
            item["location"] for item in response.data["results"]
        }

        self.assertNotIn("A+", groups)
        self.assertNotIn("Mandya", locations)

    def test_missing_parameters_return_bad_request(self):
        response = self.client.get(
            self.url,
            {"blood_group": "O+"},
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_blood_group_returns_bad_request(self):
        response = self.client.get(
            self.url,
            {"blood_group": "XYZ", "location": "Bengaluru"},
        )

        self.assertEqual(response.status_code, 400)

    def test_donor_cannot_use_cross_bank_search(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        donor = User.objects.create_user(
            username="cross_bank_donor",
            password="TestPass123!",
            role="DONOR",
        )
        self.client.force_authenticate(user=donor)

        response = self.client.get(
            self.url,
            {"blood_group": "O+", "location": "Bengaluru"},
        )

        self.assertEqual(response.status_code, 403)

    def test_search_does_not_change_stock_quantities(self):
        stock_before = list(
            BloodStock.objects.order_by("pk").values_list(
                "pk", "available_units"
            )
        )

        self.client.get(
            self.url,
            {"blood_group": "O+", "location": "Bengaluru"},
        )

        stock_after = list(
            BloodStock.objects.order_by("pk").values_list(
                "pk", "available_units"
            )
        )

        self.assertEqual(stock_before, stock_after)
