from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .models import DonorProfile
from .services import check_eligibility

User = get_user_model()
PASSWORD = "Str0ng-Pass#2024"


def years_ago(years, today=None):
    today = today or timezone.localdate()
    return today.replace(year=today.year - years) - timedelta(days=1)


def make_profile(**overrides):
    data = dict(
        date_of_birth=years_ago(25),
        weight_kg=Decimal("60"),
        last_donation_date=None,
        has_chronic_illness=False,
        on_medication=False,
        recent_surgery_or_tattoo_6_months=False,
        recent_illness_or_fever_2_weeks=False,
        is_pregnant_or_breastfeeding=False,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


class EligibilityServiceTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()

    def test_eligible_donor_never_donated(self):
        result = check_eligibility(make_profile(), today=self.today)
        self.assertTrue(result.eligible)
        self.assertEqual(result.reasons, [])
        self.assertEqual(result.next_eligible_date, self.today)

    def test_donated_30_days_ago_not_eligible(self):
        last = self.today - timedelta(days=30)
        result = check_eligibility(make_profile(last_donation_date=last), today=self.today)
        self.assertFalse(result.eligible)
        self.assertEqual(result.next_eligible_date, last + timedelta(days=90))
        self.assertTrue(any("between donations" in r for r in result.reasons))

    def test_donated_100_days_ago_eligible(self):
        last = self.today - timedelta(days=100)
        result = check_eligibility(make_profile(last_donation_date=last), today=self.today)
        self.assertTrue(result.eligible)
        self.assertEqual(result.next_eligible_date, self.today)

    def test_under_min_age(self):
        result = check_eligibility(make_profile(date_of_birth=years_ago(17)), today=self.today)
        self.assertFalse(result.eligible)
        self.assertTrue(any("at least 18 years" in r for r in result.reasons))

    def test_over_max_age(self):
        result = check_eligibility(make_profile(date_of_birth=years_ago(66)), today=self.today)
        self.assertFalse(result.eligible)
        self.assertTrue(any("at most 65 years" in r for r in result.reasons))

    def test_age_boundaries_are_eligible(self):
        exactly_18 = self.today.replace(year=self.today.year - 18)
        self.assertTrue(check_eligibility(make_profile(date_of_birth=exactly_18), today=self.today).eligible)
        exactly_65 = self.today.replace(year=self.today.year - 65)
        self.assertTrue(check_eligibility(make_profile(date_of_birth=exactly_65), today=self.today).eligible)

    def test_under_min_weight(self):
        result = check_eligibility(make_profile(weight_kg=Decimal("49.9")), today=self.today)
        self.assertFalse(result.eligible)
        self.assertTrue(any("Weight must be at least 50 kg" in r for r in result.reasons))
        self.assertTrue(check_eligibility(make_profile(weight_kg=Decimal("50")), today=self.today).eligible)

    def test_each_health_flag_blocks_with_its_reason(self):
        expected = {
            "has_chronic_illness": "chronic illness",
            "on_medication": "medication",
            "recent_surgery_or_tattoo_6_months": "surgery or a tattoo",
            "recent_illness_or_fever_2_weeks": "illness or fever",
            "is_pregnant_or_breastfeeding": "pregnant or breastfeeding",
        }
        for flag, text in expected.items():
            with self.subTest(flag=flag):
                result = check_eligibility(make_profile(**{flag: True}), today=self.today)
                self.assertFalse(result.eligible)
                self.assertEqual(len(result.reasons), 1)
                self.assertIn(text, result.reasons[0])

    def test_interval_setting_changes_next_date(self):
        last = self.today - timedelta(days=10)
        profile = make_profile(last_donation_date=last)
        with override_settings(BBMS_MIN_DONATION_INTERVAL_DAYS=30):
            result = check_eligibility(profile, today=self.today)
            self.assertEqual(result.next_eligible_date, last + timedelta(days=30))
        with override_settings(BBMS_MIN_DONATION_INTERVAL_DAYS=120):
            result = check_eligibility(profile, today=self.today)
            self.assertEqual(result.next_eligible_date, last + timedelta(days=120))

    def test_age_and_weight_limits_come_from_settings(self):
        profile = make_profile(date_of_birth=years_ago(17), weight_kg=Decimal("45"))
        with override_settings(BBMS_MIN_DONOR_AGE=16, BBMS_MIN_DONOR_WEIGHT_KG=40):
            self.assertTrue(check_eligibility(profile, today=self.today).eligible)


def profile_payload(**overrides):
    data = {
        "blood_group": "O+",
        "date_of_birth": str(years_ago(25)),
        "weight_kg": "60.0",
        "gender": "FEMALE",
        "address": "12 MG Road",
        "city": "Bangalore",
        "last_donation_date": None,
        "has_chronic_illness": False,
        "on_medication": False,
        "recent_surgery_or_tattoo_6_months": False,
        "recent_illness_or_fever_2_weeks": False,
        "is_pregnant_or_breastfeeding": False,
    }
    data.update(overrides)
    return data


class DonorApiTests(TestCase):
    def setUp(self):
        self.donor = User.objects.create_user(username="donor", password=PASSWORD, role="DONOR")
        self.staff = User.objects.create_user(username="staff", password=PASSWORD, role="STAFF")
        self.admin = User.objects.create_user(username="admin", password=PASSWORD, role="ADMIN")
        self.hospital = User.objects.create_user(username="hosp", password=PASSWORD, role="HOSPITAL")

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def test_donor_creates_and_updates_profile(self):
        client = self.client_for(self.donor)
        self.assertEqual(client.get("/api/donors/profile/").status_code, 404)

        created = client.post("/api/donors/profile/", profile_payload(), format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(DonorProfile.objects.get(user=self.donor).blood_group, "O+")

        self.assertEqual(client.post("/api/donors/profile/", profile_payload(), format="json").status_code, 409)

        updated = client.put("/api/donors/profile/", profile_payload(city="Mysore", weight_kg="65.5"), format="json")
        self.assertEqual(updated.status_code, 200)
        profile = DonorProfile.objects.get(user=self.donor)
        self.assertEqual(profile.city, "Mysore")
        self.assertEqual(profile.weight_kg, Decimal("65.5"))
        self.assertEqual(client.get("/api/donors/profile/").json()["city"], "Mysore")

    def test_eligibility_endpoint(self):
        client = self.client_for(self.donor)
        self.assertEqual(client.get("/api/donors/eligibility/").status_code, 404)
        last = timezone.localdate() - timedelta(days=30)
        client.post("/api/donors/profile/", profile_payload(last_donation_date=str(last)), format="json")
        body = client.get("/api/donors/eligibility/").json()
        self.assertFalse(body["eligible"])
        self.assertEqual(body["next_eligible_date"], str(last + timedelta(days=90)))
        self.assertTrue(body["reasons"])

    def test_non_donor_gets_403_on_profile(self):
        for user in (self.staff, self.admin, self.hospital):
            client = self.client_for(user)
            self.assertEqual(client.get("/api/donors/profile/").status_code, 403, user.username)
            self.assertEqual(client.post("/api/donors/profile/", profile_payload(), format="json").status_code, 403)
            self.assertEqual(client.get("/api/donors/eligibility/").status_code, 403)

    def test_unauthenticated_gets_401(self):
        self.assertEqual(APIClient().get("/api/donors/profile/").status_code, 401)

    def test_staff_lists_and_filters_donors(self):
        d2 = User.objects.create_user(username="donor2", password=PASSWORD, role="DONOR")
        d3 = User.objects.create_user(username="donor3", password=PASSWORD, role="DONOR")
        for user, group, city in ((self.donor, "O+", "Bangalore"), (d2, "A-", "Bangalore"), (d3, "O+", "Mysore")):
            self.client_for(user).post("/api/donors/profile/", profile_payload(blood_group=group, city=city), format="json")

        staff = self.client_for(self.staff)
        self.assertEqual(len(staff.get("/api/donors/").json()), 3)
        by_group = staff.get("/api/donors/", {"blood_group": "O+"}).json()
        self.assertEqual({d["username"] for d in by_group}, {"donor", "donor3"})
        by_city = staff.get("/api/donors/", {"city": "bangalore"}).json()
        self.assertEqual({d["username"] for d in by_city}, {"donor", "donor2"})
        both = staff.get("/api/donors/", {"blood_group": "O+", "city": "Mysore"}).json()
        self.assertEqual([d["username"] for d in both], ["donor3"])
        self.assertEqual(len(self.client_for(self.admin).get("/api/donors/").json()), 3)

    def test_unescaped_plus_in_blood_group_filter(self):
        self.client_for(self.donor).post("/api/donors/profile/", profile_payload(), format="json")
        response = self.client_for(self.staff).get("/api/donors/?blood_group=O+")
        self.assertEqual(len(response.json()), 1)

    def test_donor_and_hospital_get_403_on_list(self):
        self.assertEqual(self.client_for(self.donor).get("/api/donors/").status_code, 403)
        self.assertEqual(self.client_for(self.hospital).get("/api/donors/").status_code, 403)

    def test_list_does_not_expose_health_flags(self):
        self.client_for(self.donor).post("/api/donors/profile/", profile_payload(has_chronic_illness=True), format="json")
        row = self.client_for(self.staff).get("/api/donors/").json()[0]
        self.assertNotIn("has_chronic_illness", row)

    def test_invalid_weight_rejected(self):
        client = self.client_for(self.donor)
        for weight in ("29.9", "250.1", "-5", "abc"):
            response = client.post("/api/donors/profile/", profile_payload(weight_kg=weight), format="json")
            self.assertEqual(response.status_code, 400, weight)
            self.assertIn("weight_kg", response.json())
        self.assertFalse(DonorProfile.objects.exists())

    def test_future_date_of_birth_rejected(self):
        future = timezone.localdate() + timedelta(days=1)
        response = self.client_for(self.donor).post(
            "/api/donors/profile/", profile_payload(date_of_birth=str(future)), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("date_of_birth", response.json())

    def test_future_last_donation_date_rejected(self):
        future = timezone.localdate() + timedelta(days=1)
        response = self.client_for(self.donor).post(
            "/api/donors/profile/", profile_payload(last_donation_date=str(future)), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_required_fields_and_underage_can_register(self):
        client = self.client_for(self.donor)
        response = client.post("/api/donors/profile/", {"blood_group": "O+"}, format="json")
        self.assertEqual(response.status_code, 400)
        # age and weight are checked for eligibility, not for registration
        young = client.post(
            "/api/donors/profile/",
            profile_payload(date_of_birth=str(years_ago(16)), weight_kg="40"),
            format="json",
        )
        self.assertEqual(young.status_code, 201)
        self.assertFalse(client.get("/api/donors/eligibility/").json()["eligible"])

    def test_invalid_blood_group_rejected(self):
        response = self.client_for(self.donor).post(
            "/api/donors/profile/", profile_payload(blood_group="Z+"), format="json"
        )
        self.assertEqual(response.status_code, 400)


class DonorWebTests(TestCase):
    def setUp(self):
        self.donor = User.objects.create_user(username="webdonor", password=PASSWORD, role="DONOR")
        self.staff = User.objects.create_user(username="webstaff", password=PASSWORD, role="STAFF")

    def test_dashboard_without_profile_prompts_to_complete(self):
        self.client.force_login(self.donor)
        response = self.client.get("/dashboard/donor/")
        self.assertContains(response, "Welcome, webdonor")
        self.assertContains(response, "Complete your donor profile")

    def test_profile_form_creates_profile_and_dashboard_shows_status(self):
        self.client.force_login(self.donor)
        self.assertEqual(self.client.get("/donors/profile/").status_code, 200)
        response = self.client.post(
            "/donors/profile/",
            {
                "blood_group": "B+",
                "date_of_birth": str(years_ago(30)),
                "weight_kg": "70",
                "gender": "MALE",
                "address": "Somewhere",
                "city": "Pune",
            },
        )
        self.assertRedirects(response, "/dashboard/donor/")
        dashboard = self.client.get("/dashboard/donor/")
        self.assertContains(dashboard, "B+")
        self.assertContains(dashboard, "Eligible")
        self.assertNotContains(dashboard, "Not eligible")

    def test_dashboard_shows_not_eligible_with_reasons(self):
        DonorProfile.objects.create(
            user=self.donor,
            blood_group="A+",
            date_of_birth=years_ago(30),
            weight_kg=Decimal("70"),
            gender="MALE",
            address="x",
            city="Pune",
            on_medication=True,
        )
        self.client.force_login(self.donor)
        response = self.client.get("/dashboard/donor/")
        self.assertContains(response, "Not eligible")
        self.assertContains(response, "currently on medication")

    def test_profile_form_edit_prefills_and_updates(self):
        self.client.force_login(self.donor)
        base = {
            "blood_group": "B+",
            "date_of_birth": str(years_ago(30)),
            "weight_kg": "70",
            "gender": "MALE",
            "address": "Somewhere",
            "city": "Pune",
        }
        self.client.post("/donors/profile/", base)
        self.assertContains(self.client.get("/donors/profile/"), "Pune")
        self.client.post("/donors/profile/", {**base, "city": "Delhi"})
        self.assertEqual(DonorProfile.objects.count(), 1)
        self.assertEqual(DonorProfile.objects.get().city, "Delhi")

    def test_profile_form_rejects_invalid_weight(self):
        self.client.force_login(self.donor)
        response = self.client.post(
            "/donors/profile/",
            {"blood_group": "B+", "date_of_birth": str(years_ago(30)), "weight_kg": "10",
             "gender": "MALE", "address": "x", "city": "Pune"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DonorProfile.objects.exists())

    def test_non_donor_forbidden_and_anonymous_redirected(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/donors/profile/").status_code, 403)
        self.assertEqual(self.client.get("/dashboard/donor/").status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.get("/donors/profile/"), "/login/?next=/donors/profile/")
