from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()
STRONG = "Str0ng-Pass#2024"


class AuthApiTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def register(self, **overrides):
        data = {
            "username": "alice",
            "email": "alice@example.com",
            "password": STRONG,
            "role": "DONOR",
            "phone": "9999999999",
        }
        data.update(overrides)
        return self.api.post("/api/auth/register/", data, format="json")

    def test_register_donor_succeeds_and_hashes_password(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("password", response.json())
        user = User.objects.get(username="alice")
        self.assertEqual(user.role, "DONOR")
        self.assertNotEqual(user.password, STRONG)
        self.assertTrue(user.check_password(STRONG))

    def test_register_hospital_succeeds(self):
        self.assertEqual(self.register(username="h1", role="HOSPITAL").status_code, 201)

    def test_register_staff_or_admin_rejected(self):
        for role in ("STAFF", "ADMIN"):
            response = self.register(username=f"x{role}", role=role)
            self.assertEqual(response.status_code, 400)
            self.assertFalse(User.objects.filter(username=f"x{role}").exists())

    def test_weak_password_rejected(self):
        for weak in ("12345678", "password", "short1"):
            self.assertEqual(self.register(password=weak).status_code, 400)
        self.assertFalse(User.objects.filter(username="alice").exists())

    def test_login_returns_tokens_and_role(self):
        self.register()
        response = self.api.post(
            "/api/auth/login/", {"username": "alice", "password": STRONG}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("access", body)
        self.assertIn("refresh", body)
        self.assertEqual(body["role"], "DONOR")
        self.assertEqual(body["username"], "alice")

    def test_refresh_returns_new_access_token(self):
        self.register()
        tokens = self.api.post(
            "/api/auth/login/", {"username": "alice", "password": STRONG}, format="json"
        ).json()
        response = self.api.post(
            "/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())

    def test_wrong_password_returns_401(self):
        self.register()
        response = self.api.post(
            "/api/auth/login/", {"username": "alice", "password": "wrong"}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_me_requires_token(self):
        self.assertEqual(self.api.get("/api/auth/me/").status_code, 401)
        self.register()
        tokens = self.api.post(
            "/api/auth/login/", {"username": "alice", "password": STRONG}, format="json"
        ).json()
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        response = self.api.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "alice")
        self.assertEqual(response.json()["role"], "DONOR")


class DashboardTests(TestCase):
    ROLES = {
        "DONOR": "/dashboard/donor/",
        "STAFF": "/dashboard/staff/",
        "HOSPITAL": "/dashboard/hospital/",
        "ADMIN": "/dashboard/admin/",
    }

    def setUp(self):
        for role in self.ROLES:
            User.objects.create_user(username=role.lower(), password=STRONG, role=role)

    def test_each_role_redirected_to_own_dashboard(self):
        for role, url in self.ROLES.items():
            client = self.client_class()
            self.assertTrue(client.login(username=role.lower(), password=STRONG))
            self.assertRedirects(client.get("/dashboard/"), url)
            response = client.get(url)
            self.assertContains(response, f"Welcome, {role.lower()}")

    def test_other_roles_dashboards_forbidden(self):
        for role, own in self.ROLES.items():
            client = self.client_class()
            client.login(username=role.lower(), password=STRONG)
            for other_role, url in self.ROLES.items():
                if other_role != role:
                    self.assertEqual(client.get(url).status_code, 403, (role, url))

    def test_anonymous_redirected_to_login(self):
        response = self.client.get("/dashboard/donor/")
        self.assertRedirects(response, "/login/?next=/dashboard/donor/")

    def test_web_register_and_login_pages(self):
        for url in ("/register/", "/login/"):
            self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(
            "/register/",
            {
                "username": "newdonor",
                "email": "n@example.com",
                "phone": "1",
                "role": "DONOR",
                "password1": STRONG,
                "password2": STRONG,
            },
        )
        self.assertRedirects(response, "/dashboard/", fetch_redirect_response=False)
        self.assertEqual(User.objects.get(username="newdonor").role, "DONOR")

    def test_web_register_rejects_staff_role(self):
        response = self.client.post(
            "/register/",
            {"username": "sneaky", "role": "STAFF", "password1": STRONG, "password2": STRONG},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="sneaky").exists())


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
