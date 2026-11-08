from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from bloodrequests.models import BloodRequest
from inventory.models import BloodStock

User = get_user_model()


class WebTestBase(TestCase):
    def setUp(self):
        for role in ("hospital", "staff", "admin", "donor"):
            setattr(
                self,
                role,
                User.objects.create_user(
                    username=f"{role}_web", password="TestPass123!", role=role.upper()
                ),
            )

    def get_as(self, user, url_name):
        self.client.force_login(user)
        return self.client.get(reverse(url_name))


class DashboardLinkTests(WebTestBase):
    def assertLink(self, user, dashboard, *url_names):
        response = self.get_as(user, dashboard)
        self.assertEqual(response.status_code, 200)
        for name in url_names:
            self.assertContains(response, f'href="{reverse(name)}"')

    def test_nav_has_camps_link_for_logged_in_users(self):
        for user in (self.hospital, self.staff, self.admin, self.donor):
            self.client.force_login(user)
            response = self.client.get(reverse("profile"))
            self.assertContains(response, f'href="{reverse("camp-list")}"')

    def test_nav_has_no_camps_link_for_anonymous(self):
        response = self.client.get(reverse("home"))
        self.assertNotContains(response, f'href="{reverse("camp-list")}"')

    def test_staff_dashboard_links(self):
        self.assertLink(
            self.staff, "dashboard-staff", "camp-manage", "blood-request-process-page", "inventory-page"
        )

    def test_admin_dashboard_links(self):
        self.assertLink(
            self.admin, "dashboard-admin", "camp-manage", "blood-request-process-page", "inventory-page"
        )

    def test_donor_dashboard_links(self):
        self.assertLink(self.donor, "dashboard-donor", "camp-list")

    def test_hospital_dashboard_links(self):
        self.assertLink(
            self.hospital,
            "dashboard-hospital",
            "blood-availability-page",
            "blood-request-new",
            "blood-request-mine",
        )


class HospitalRequestPageTests(WebTestBase):
    def test_hospital_can_open_pages(self):
        self.client.force_login(self.hospital)
        for name in ("blood-request-new", "blood-request-mine", "blood-availability-page"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_submit_emergency_request_appears_in_my_requests(self):
        self.client.force_login(self.hospital)
        response = self.client.post(
            reverse("blood-request-new"),
            {"blood_group": "O+", "units": 3, "location": "Bengaluru", "priority": "emergency"},
            follow=True,
        )
        self.assertRedirects(response, reverse("blood-request-mine"))
        self.assertContains(response, "Blood request submitted.")
        blood_request = BloodRequest.objects.get(requester=self.hospital)
        self.assertEqual(blood_request.status, BloodRequest.RequestStatus.PENDING)
        self.assertContains(response, str(blood_request.request_id))
        self.assertContains(response, "O+")

    def test_scheduled_request_needs_future_date(self):
        self.client.force_login(self.hospital)
        data = {"blood_group": "A+", "units": 1, "location": "Mysuru", "priority": "scheduled"}

        response = self.client.post(reverse("blood-request-new"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "A required date is needed for scheduled requests.")

        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.client.post(reverse("blood-request-new"), {**data, "required_date": past})
        self.assertContains(response, "The required date cannot be in the past.")
        self.assertEqual(BloodRequest.objects.count(), 0)

        future = (timezone.localdate() + timedelta(days=3)).isoformat()
        response = self.client.post(reverse("blood-request-new"), {**data, "required_date": future})
        self.assertRedirects(response, reverse("blood-request-mine"))
        self.assertEqual(BloodRequest.objects.count(), 1)

    def test_my_requests_only_shows_own_requests_newest_first(self):
        other = User.objects.create_user(username="other_hosp", password="x", role="HOSPITAL")
        mine = [
            BloodRequest.objects.create(
                requester=self.hospital, blood_group="B+", units=1,
                location="X", priority="emergency",
            )
            for _ in range(2)
        ]
        theirs = BloodRequest.objects.create(
            requester=other, blood_group="B+", units=1, location="X", priority="emergency"
        )
        response = self.get_as(self.hospital, "blood-request-mine")
        self.assertNotContains(response, str(theirs.request_id))
        content = response.content.decode()
        self.assertLess(
            content.index(str(mine[1].request_id)), content.index(str(mine[0].request_id))
        )

    def test_non_hospital_roles_get_403_on_request_pages(self):
        for user in (self.donor, self.staff, self.admin):
            for name in ("blood-request-new", "blood-request-mine"):
                self.assertEqual(self.get_as(user, name).status_code, 403, (user.role, name))

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("blood-request-new"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])


class AvailabilityPageTests(WebTestBase):
    def setUp(self):
        super().setUp()
        today = timezone.localdate()
        BloodStock.objects.create(
            blood_group="O+", location="Bengaluru", available_units=7,
            collection_date=today, expiry_date=today + timedelta(days=20),
        )

    def search(self, user, **params):
        self.client.force_login(user)
        return self.client.get(reverse("blood-availability-page"), params)

    def test_hospital_staff_admin_can_search(self):
        for user in (self.hospital, self.staff, self.admin):
            response = self.search(user, blood_group="O+", location="bengaluru")
            self.assertEqual(response.status_code, 200, user.role)
            self.assertContains(response, "7 units of O+ available at bengaluru")

    def test_no_stock_message(self):
        response = self.search(self.hospital, blood_group="AB-", location="Bengaluru")
        self.assertContains(response, "No available blood stock found")

    def test_donor_gets_403(self):
        self.assertEqual(self.get_as(self.donor, "blood-availability-page").status_code, 403)


class StaffWorkflowPagesTests(TestCase):
    """Stock in -> hospital request -> staff approval -> cancel, all through web pages."""

    def setUp(self):
        self.hospital = User.objects.create_user(username="wf_hosp", password="TestPass123!", role="HOSPITAL")
        self.staff = User.objects.create_user(username="wf_staff", password="TestPass123!", role="STAFF")
        self.donor = User.objects.create_user(username="wf_donor", password="TestPass123!", role="DONOR")
        self.today = timezone.localdate()

    def add_units(self, quantity):
        self.client.force_login(self.staff)
        return self.client.post(reverse("inventory-page"), {
            "blood_group": "A+",
            "quantity": quantity,
            "collection_date": self.today - timedelta(days=1),
            "expiry_date": self.today + timedelta(days=20),
            "bank_location": "Pune",
        })

    def submit_request(self, units):
        self.client.force_login(self.hospital)
        self.client.post(reverse("blood-request-new"), {
            "blood_group": "A+",
            "units": units,
            "location": "Pune",
            "priority": BloodRequest.Priority.EMERGENCY,
        })
        return BloodRequest.objects.latest("created_at")

    def act(self, blood_request, status):
        self.client.force_login(self.staff)
        return self.client.post(
            reverse("blood-request-action", args=[blood_request.request_id]),
            {"status": status},
            follow=True,
        )

    def test_full_workflow(self):
        self.assertEqual(self.add_units(5).status_code, 302)
        stock = BloodStock.objects.get(location="Pune")
        self.assertEqual(stock.available_units, 5)

        blood_request = self.submit_request(3)
        self.assertEqual(blood_request.status, BloodRequest.RequestStatus.PENDING)

        self.client.force_login(self.staff)
        page = self.client.get(reverse("blood-request-process-page"))
        self.assertContains(page, "Approve")

        response = self.act(blood_request, "approved")
        self.assertContains(response, "Request approved")
        blood_request.refresh_from_db()
        stock.refresh_from_db()
        self.assertEqual(blood_request.status, BloodRequest.RequestStatus.APPROVED)
        self.assertEqual(stock.available_units, 2)

        self.client.force_login(self.hospital)
        response = self.client.post(
            reverse("blood-request-cancel-page", args=[blood_request.request_id]), follow=True
        )
        self.assertContains(response, "Request cancelled")
        stock.refresh_from_db()
        self.assertEqual(stock.available_units, 5)

    def test_insufficient_stock_shows_reason(self):
        self.add_units(1)
        blood_request = self.submit_request(4)
        response = self.act(blood_request, "approved")
        self.assertContains(response, "Insufficient compatible blood stock")
        blood_request.refresh_from_db()
        self.assertEqual(blood_request.status, BloodRequest.RequestStatus.PENDING)

    def test_reject_and_invalid_transition(self):
        blood_request = self.submit_request(1)
        self.assertContains(self.act(blood_request, "rejected"), "Request rejected")
        self.assertContains(self.act(blood_request, "approved"), "Only pending requests can be approved")

    def test_invalid_unit_dates_rejected(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("inventory-page"), {
            "blood_group": "A+", "quantity": 2,
            "collection_date": self.today, "expiry_date": self.today,
            "bank_location": "Pune",
        })
        self.assertContains(response, "Expiry date must be after collection date.")

    def test_role_restrictions(self):
        self.client.force_login(self.donor)
        self.assertEqual(self.client.get(reverse("blood-request-process-page")).status_code, 403)
        self.assertEqual(self.client.get(reverse("inventory-page")).status_code, 403)
        self.client.force_login(self.hospital)
        self.assertEqual(self.client.get(reverse("blood-request-process-page")).status_code, 403)
        blood_request = self.submit_request(1)
        response = self.client.post(reverse("blood-request-action", args=[blood_request.request_id]), {"status": "approved"})
        self.assertEqual(response.status_code, 403)
