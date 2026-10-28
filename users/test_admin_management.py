
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class AdminUserManagementTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.admin = User.objects.create_user(
            username="admin1",
            email="admin@example.com",
            password="Str0ng-Pass#2024",
            role=User.Role.ADMIN,
        )
        self.donor = User.objects.create_user(
            username="donor1",
            email="donor@example.com",
            password="Str0ng-Pass#2024",
            role=User.Role.DONOR,
        )

    def test_anonymous_user_cannot_list_accounts(self):
        response = self.api.get("/api/auth/admin/users/")
        self.assertEqual(response.status_code, 401)

    def test_non_admin_cannot_list_accounts(self):
        self.api.force_authenticate(user=self.donor)
        response = self.api.get("/api/auth/admin/users/")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_list_accounts(self):
        self.api.force_authenticate(user=self.admin)
        response = self.api.get("/api/auth/admin/users/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 2)

    def test_admin_can_create_account_with_hashed_password(self):
        self.api.force_authenticate(user=self.admin)
        response = self.api.post(
            "/api/auth/admin/users/",
            {
                "username": "staff1",
                "email": "staff@example.com",
                "role": "STAFF",
                "password": "An0ther-Strong#2026",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="staff1")
        self.assertTrue(user.check_password("An0ther-Strong#2026"))
        self.assertNotIn("password", response.data)

    def test_admin_can_create_hospital_account(self):
        self.api.force_authenticate(user=self.admin)

        response = self.api.post(
            "/api/auth/admin/users/",
            {
                "username": "hospital1",
                "email": "hospital@example.com",
                "role": "HOSPITAL",
                "password": "H0spital-Strong#2026",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        hospital = User.objects.get(username="hospital1")
        self.assertEqual(hospital.role, User.Role.HOSPITAL)
        self.assertTrue(
            hospital.check_password("H0spital-Strong#2026")
        )

    def test_admin_can_deactivate_account(self):
        self.api.force_authenticate(user=self.admin)
        response = self.api.patch(
            f"/api/auth/admin/users/{self.donor.pk}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.donor.refresh_from_db()
        self.assertFalse(self.donor.is_active)

    def test_admin_cannot_delete_own_account(self):
        self.api.force_authenticate(user=self.admin)
        response = self.api.delete(
            f"/api/auth/admin/users/{self.admin.pk}/"
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            User.objects.filter(pk=self.admin.pk).exists()
        )
