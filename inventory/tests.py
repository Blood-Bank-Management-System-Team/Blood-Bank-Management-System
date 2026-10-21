
from rest_framework.test import APITestCase

from users.models import User
from .models import BloodUnit


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
            self.list_url, data, format="json"
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
            response.data[0]["bank_location"], "Test Blood Bank"
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
            self.list_url, {"available": "true"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_available_filter_includes_non_expired_units(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            self.list_url, {"available": "true"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertFalse(response.data[0]["is_expired"])

    def test_available_filter_excludes_zero_quantity_units(self):
        self.unit.quantity = 0
        self.unit.save()

        self.client.force_authenticate(user=self.staff)
        response = self.client.get(
            self.list_url, {"available": "true"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)
