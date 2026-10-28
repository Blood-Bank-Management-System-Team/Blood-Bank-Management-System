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


# ---------- BB-17: reports and analytics ----------
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from bloodrequests.models import BloodRequest
from donors.models import DonationRecord
from inventory.models import BloodStock
from notifications.models import LowStockThreshold


class ReportsTests(TestCase):
    URL = "/api/reports/summary/"

    @classmethod
    def setUpTestData(cls):
        cls.today = timezone.localdate()
        cls.admin = User.objects.create_user("rep_admin", password=PASSWORD, role="ADMIN")
        cls.staff = User.objects.create_user("rep_staff", password=PASSWORD, role="STAFF")
        cls.hospital = User.objects.create_user("rep_hosp", password=PASSWORD, role="HOSPITAL")
        cls.donor_user = User.objects.create_user("rep_donor", password=PASSWORD, role="DONOR")
        donor = DonorProfile.objects.create(
            user=cls.donor_user, blood_group="O+", date_of_birth=date(1995, 1, 1),
            weight_kg=Decimal("60"), gender="MALE", address="x", city="Pune",
        )

        def days_ago(n):
            return cls.today - timedelta(days=n)

        # donations: 3 in the default range (units 1+2+1), 1 old
        for n, units in ((2, 1), (2, 2), (10, 1), (60, 2)):
            DonationRecord.objects.create(
                donor=donor, donation_date=days_ago(n), blood_bank_location="Main", units=units)

        def stock(group, units, status="AVAILABLE", expiry=None):
            return BloodStock.objects.create(
                blood_group=group, location="Main", available_units=units,
                collection_date=days_ago(30), expiry_date=expiry or days_ago(-20), status=status,
            )

        stock("O+", 10)
        stock("O+", 5)                       # O+ total 15
        stock("A+", 3)                       # below the A+ threshold of 5
        stock("B+", 7, status="RESERVED")    # excluded
        stock("B+", 4, expiry=days_ago(5))   # excluded (expired)
        stock("AB+", 6, status="DISPOSED")   # excluded from stock, counted as wastage
        LowStockThreshold.objects.create(blood_group="A+", minimum_quantity=5)
        LowStockThreshold.objects.create(blood_group="O+", minimum_quantity=5)

        # wastage: AB+ 6 units disposed 3 days ago after expiring ("expired");
        # O- 2 units disposed 40 days ago while still in date ("other")
        old = stock("O-", 2, status="DISPOSED")
        BloodStock.objects.filter(blood_group="AB+", status="DISPOSED").update(
            updated_at=timezone.now() - timedelta(days=3), expiry_date=days_ago(20))
        BloodStock.objects.filter(pk=old.pk).update(updated_at=timezone.now() - timedelta(days=40))

        def req(group, priority, status, age=1):
            r = BloodRequest.objects.create(
                requester=cls.hospital, blood_group=group, units=2, location="H",
                priority=priority, status=status)
            BloodRequest.objects.filter(pk=r.pk).update(created_at=timezone.now() - timedelta(days=age))

        req("O+", "emergency", "pending")
        req("A+", "scheduled", "pending")
        req("B+", "emergency", "approved")
        req("O+", "scheduled", "rejected")
        req("O+", "scheduled", "fulfilled")
        req("O+", "emergency", "fulfilled", age=90)  # outside the default range

    def api(self, user=None, **params):
        client = APIClient()
        if user:
            client.force_authenticate(user)
        return client.get(self.URL, params)

    # --- numbers ---
    def test_summary_totals(self):
        data = self.api(self.admin).json()
        self.assertEqual(data["donations"]["total_units"], 4)
        self.assertEqual(data["donations"]["total_donations"], 3)
        self.assertEqual(len(data["donations"]["daily"]), 31)
        by_day = {r["date"]: r for r in data["donations"]["daily"]}
        two = (self.today - timedelta(days=2)).isoformat()
        self.assertEqual((by_day[two]["units"], by_day[two]["donations"]), (3, 2))

        stock = {g["blood_group"]: g["units"] for g in data["stock"]["groups"]}
        self.assertEqual(stock["O+"], 15)
        self.assertEqual(stock["A+"], 3)
        self.assertEqual(stock["B+"], 0)   # reserved and expired excluded
        self.assertEqual(stock["AB+"], 0)  # disposed excluded
        self.assertEqual(data["stock"]["total_units"], 18)

        req = data["requests"]
        self.assertEqual(req["total"], 5)
        self.assertEqual(
            req["by_status"],
            {
                "pending": 2,
                "approved": 1,
                "rejected": 1,
                "fulfilled": 1,
                "cancelled": 0,
            },
        )
        self.assertEqual(req["by_priority"], {"emergency": 2, "scheduled": 3})

        wastage = data["wastage"]
        self.assertEqual(wastage["total_units"], 6)
        self.assertEqual(wastage["by_blood_group"]["AB+"], 6)
        self.assertEqual(wastage["by_blood_group"]["O-"], 0)  # outside the range
        self.assertEqual(wastage["by_reason"], {"expired": 6, "other": 0})

    def test_low_stock_group_flagged(self):
        stock = self.api(self.admin).json()["stock"]
        self.assertEqual(stock["low_stock_groups"], ["A+"])
        flags = {g["blood_group"]: g["low_stock"] for g in stock["groups"]}
        self.assertTrue(flags["A+"])
        self.assertFalse(flags["O+"])
        self.assertFalse(flags["B+"])  # no threshold configured

    def test_date_filter_changes_numbers(self):
        wide = self.api(self.admin, date_from=(self.today - timedelta(days=100)).isoformat(),
                        date_to=self.today.isoformat()).json()
        self.assertEqual(wide["donations"]["total_units"], 6)
        self.assertEqual(wide["wastage"]["by_blood_group"]["O-"], 2)
        self.assertEqual(wide["wastage"]["by_reason"], {"expired": 6, "other": 2})
        self.assertEqual(wide["requests"]["total"], 6)
        narrow = self.api(self.admin, date_from=(self.today - timedelta(days=5)).isoformat(),
                          date_to=self.today.isoformat()).json()
        self.assertEqual(narrow["donations"]["total_units"], 3)

    # --- validation and permissions ---
    def test_invalid_dates_return_400(self):
        r = self.api(self.admin, date_from="2024-13-45")
        self.assertEqual(r.status_code, 400)
        self.assertIn("YYYY-MM-DD", str(r.json()))
        r = self.api(self.admin, date_from="2025-02-01", date_to="2025-01-01")
        self.assertEqual(r.status_code, 400)
        self.assertIn("date_from", r.json())

    def test_permissions(self):
        self.assertEqual(self.api().status_code, 401)
        self.assertEqual(self.api(self.donor_user).status_code, 403)
        self.assertEqual(self.api(self.hospital).status_code, 403)
        self.assertEqual(self.api(self.admin).status_code, 200)
        self.assertEqual(self.api(self.staff).status_code, 200)

    # --- page and CSV ---
    def test_page_renders_for_admin(self):
        c = Client()
        c.force_login(self.admin)
        r = c.get("/reports/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        for canvas in ("chart-donations", "chart-stock", "chart-requests", "chart-wastage"):
            self.assertIn(f'id="{canvas}"', html)
        for tile in ("tile-donations", "tile-stock", "tile-pending", "tile-wasted"):
            self.assertIn(f'id="{tile}"', html)
        self.assertIn('id="chart-data"', html)
        self.assertIn("chart.js@4.4.1", html)
        self.assertIn("Low stock: A+", html)

    def test_page_empty_state_and_access(self):
        c = Client()
        self.assertEqual(c.get("/reports/").status_code, 302)
        c.force_login(self.hospital)
        self.assertEqual(c.get("/reports/").status_code, 403)
        c.force_login(self.staff)
        r = c.get("/reports/", {"date_from": "2000-01-01", "date_to": "2000-01-01"})
        self.assertContains(r, "No data for this period")

    def test_csv_export(self):
        c = Client()
        c.force_login(self.staff)
        r = c.get("/reports/export.csv")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Type"].startswith("text/csv"))
        body = r.content.decode()
        for header in ("Donations collected", "Donations per day", "Available stock by blood group",
                       "Blood requests by status", "Blood requests by priority",
                       "Wastage by blood group", "Wastage by reason"):
            self.assertIn(header, body)
        c.force_login(self.donor_user)
        self.assertEqual(c.get("/reports/export.csv").status_code, 403)
        c.force_login(self.admin)
        self.assertEqual(c.get("/reports/export.csv", {"date_from": "bad"}).status_code, 400)

    # --- performance ---
    def test_summary_query_count_is_small_and_fixed(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        with CaptureQueriesContext(connection) as first:
            client.get(self.URL)
        self.assertLessEqual(len(first), 10, [q["sql"] for q in first])
        for group in ("A-", "B-", "AB-"):  # more data must not add queries
            BloodStock.objects.create(
                blood_group=group, location="Main", available_units=1,
                collection_date=self.today, expiry_date=self.today + timedelta(days=9))
        with CaptureQueriesContext(connection) as second:
            client.get(self.URL)
        self.assertEqual(len(first), len(second))
