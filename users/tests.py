from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class SkeletonTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_home_page_loads_with_title(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blood Bank Management System")

    def test_new_user_defaults_to_donor(self):
        user = User.objects.create_user(username="donor1", password="pass12345!")
        self.assertEqual(user.role, User.Role.DONOR)

    def test_password_is_hashed(self):
        user = User.objects.create_user(username="donor2", password="pass12345!")
        self.assertNotEqual(user.password, "pass12345!")
        self.assertTrue(user.check_password("pass12345!"))
