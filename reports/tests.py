from datetime import date, timedelta
from decimal import Decimal

from django.apps import apps
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from donors.models import DonorProfile

from .admin import AuditLogAdmin
from .models import AuditLog

User = get_user_model()
PASSWORD = "Str0ng-Pass#2024"
PROFILE = {
    "blood_group": "O+", "date_of_birth": "1995-01-01", "weight_kg": "60.0", "gender": "MALE",
    "address": "x", "city": "Pune",
}


class AuditSignalTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def test_donor_profile_create_and_update_logged_with_user(self):
        donor = User.objects.create_user("donor1", password=PASSWORD, role="DONOR")
        self.api.force_authenticate(donor)
        self.assertEqual(self.api.post("/api/donors/profile/", PROFILE, format="json").status_code, 201)
        profile = DonorProfile.objects.get(user=donor)
        create = AuditLog.objects.get(action="CREATE", model_name="DonorProfile")
        self.assertEqual(create.user, donor)
        self.assertEqual(create.object_id, str(profile.pk))

        self.assertEqual(self.api.put("/api/donors/profile/", {**PROFILE, "city": "Delhi"}, format="json").status_code, 200)
        update = AuditLog.objects.get(action="UPDATE", model_name="DonorProfile")
        self.assertEqual(update.user, donor)
        self.assertIn("city", update.description)
        self.assertNotIn("Delhi", update.description)

    def test_unchanged_save_not_logged(self):
        donor = User.objects.create_user("d", password=PASSWORD, role="DONOR")
        profile = DonorProfile.objects.create(
            user=donor, blood_group="O+", date_of_birth=date(1995, 1, 1), weight_kg=Decimal("60"),
            gender="MALE", address="x", city="Pune",
        )
        AuditLog.objects.all().delete()
        profile.save()
        self.assertFalse(AuditLog.objects.exists())

    def test_user_role_change_logged(self):
        user = User.objects.create_user("u", password=PASSWORD, role="DONOR")
        user.role = "STAFF"
        user.save()
        log = AuditLog.objects.get(model_name="User", action="UPDATE")
        self.assertIn("role", log.description)
        self.assertNotIn("password", log.description.lower())

    def test_blood_request_status_actions(self):
        try:
            BloodRequest = apps.get_model("bloodrequests.BloodRequest")
        except LookupError:
            self.skipTest("BloodRequest model not present")
        hospital = User.objects.create_user("h", password=PASSWORD, role="HOSPITAL")
        admin_user = User.objects.create_user("a", password=PASSWORD, role="ADMIN")
        req = BloodRequest.objects.create(
            requester=hospital, blood_group="O+", units=2, location="X", priority="scheduled"
        )
        self.assertTrue(AuditLog.objects.filter(action="CREATE", model_name="BloodRequest").exists())
        for status, action in (("approved", "APPROVE"), ("fulfilled", "FULFIL"), ("rejected", "REJECT")):
            req.status = status
            req.save()
            self.assertTrue(AuditLog.objects.filter(action=action, object_id=str(req.pk)).exists(), action)
        self.assertEqual(AuditLog.objects.filter(action="UPDATE", model_name="BloodRequest").count(), 0)
        # acting user captured through middleware on a real request
        req2 = BloodRequest.objects.create(
            requester=hospital, blood_group="A+", units=1, location="X", priority="scheduled"
        )
        self.assertIsNone(AuditLog.objects.filter(action="CREATE", object_id=str(req2.pk)).first().user)
        self.assertIsNotNone(admin_user)

    def test_login_logged(self):
        user = User.objects.create_user("alice", password=PASSWORD)
        self.assertTrue(self.client.login(username="alice", password=PASSWORD))
        log = AuditLog.objects.get(action="LOGIN")
        self.assertEqual(log.user, user)

    def test_failed_login_has_no_password(self):
        User.objects.create_user("alice", password=PASSWORD)
        bad = "Wr0ng-Secret#999"
        self.client.post("/login/", {"username": "alice", "password": bad})
        log = AuditLog.objects.get(action="LOGIN_FAILED")
        self.assertIsNone(log.user)
        self.assertIn("alice", log.description)
        for field in (log.description, log.model_name, log.object_id):
            self.assertNotIn(bad, field)
        self.assertEqual(log.ip_address, "127.0.0.1")

    def test_logging_failure_does_not_break_action(self):
        from unittest import mock

        with mock.patch("reports.audit.AuditLog.objects.create", side_effect=RuntimeError("db down")):
            with self.assertLogs("reports.audit", level="WARNING"):
                user = User.objects.create_user("x", password=PASSWORD, role="DONOR")
                user.role = "STAFF"
                user.save()
        user.refresh_from_db()
        self.assertEqual(user.role, "STAFF")


class AuditApiTests(TestCase):
    URL = "/api/reports/audit-logs/"

    def setUp(self):
        self.api = APIClient()
        self.admin = User.objects.create_user("boss", password=PASSWORD, role="ADMIN")
        self.staff = User.objects.create_user("st", password=PASSWORD, role="STAFF")
        self.donor = User.objects.create_user("dn", password=PASSWORD, role="DONOR")
        AuditLog.objects.all().delete()
        self.a = AuditLog.objects.create(user=self.admin, action="CREATE", model_name="DonorProfile", object_id="1")
        self.b = AuditLog.objects.create(user=self.staff, action="DELETE", model_name="BloodUnit", object_id="2")
        old = timezone.now() - timedelta(days=10)
        AuditLog.objects.filter(pk=self.b.pk).update(timestamp=old)

    def test_access_control(self):
        self.assertEqual(self.api.get(self.URL).status_code, 401)
        for user in (self.staff, self.donor):
            self.api.force_authenticate(user)
            self.assertEqual(self.api.get(self.URL).status_code, 403)

    def test_admin_lists_newest_first_paginated(self):
        self.api.force_authenticate(self.admin)
        data = self.api.get(self.URL).json()
        self.assertEqual(data["count"], 2)
        self.assertEqual([r["id"] for r in data["results"]], [self.a.id, self.b.id])

    def test_filters(self):
        self.api.force_authenticate(self.admin)
        ids = lambda q: [r["id"] for r in self.api.get(self.URL + q).json()["results"]]  # noqa: E731
        self.assertEqual(ids("?action=DELETE"), [self.b.id])
        self.assertEqual(ids("?user=boss"), [self.a.id])
        self.assertEqual(ids("?model=BloodUnit"), [self.b.id])
        today = timezone.localdate().isoformat()
        self.assertEqual(ids(f"?date_from={today}"), [self.a.id])
        self.assertEqual(ids(f"?date_to={(timezone.localdate() - timedelta(days=5)).isoformat()}"), [self.b.id])
        self.assertEqual(self.api.get(self.URL + "?date_from=bad").status_code, 400)
        self.assertEqual(self.api.get(self.URL + "?action=NOPE").status_code, 400)

    def test_page_admin_only(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/reports/audit/").status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get("/reports/audit/?action=CREATE")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DonorProfile")
        self.assertNotContains(response, "BloodUnit</td>")

    def test_admin_page_links_to_audit_log(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/dashboard/admin/"), "/reports/audit/")


class AuditAdminTests(TestCase):
    def test_read_only_in_admin(self):
        model_admin = AuditLogAdmin(AuditLog, admin.site)
        superuser = User.objects.create_superuser("root", password=PASSWORD)
        request = RequestFactory().get("/")
        request.user = superuser
        log = AuditLog.objects.create(action="OTHER")
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request, log))
        self.assertFalse(model_admin.has_delete_permission(request, log))
        self.assertTrue(model_admin.has_view_permission(request, log))
