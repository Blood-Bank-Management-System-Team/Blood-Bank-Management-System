
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from camps.models import CampDonation, CampRegistration, DonationCamp
from donors.models import DonationRecord, DonorProfile
from inventory.models import BloodUnit
from users.models import User


class CampDonationRecordTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="camp_staff",
            password="test-password-123",
            role=User.Role.STAFF,
        )

        self.donor_user = User.objects.create_user(
            username="camp_donor",
            password="test-password-123",
            role=User.Role.DONOR,
        )

        self.donor = DonorProfile.objects.create(
            user=self.donor_user,
            blood_group="O+",
            date_of_birth=timezone.localdate() - timedelta(days=25 * 365),
            weight_kg=60,
            gender="MALE",
            address="Test Address",
            city="Bengaluru",
        )

        self.camp = DonationCamp.objects.create(
            name="Test Blood Donation Camp",
            description="Camp for automated tests",
            date=timezone.localdate(),
            venue="Test Blood Bank",
            available_slots=10,
            created_by=self.staff,
        )

        self.registration = CampRegistration.objects.create(
            camp=self.camp,
            donor=self.donor,
        )

        self.url = reverse(
            "camp-record-donation",
            kwargs={"pk": self.camp.pk},
        )

    def test_staff_can_open_donation_form(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_donor_cannot_open_donation_form(self):
        self.client.force_login(self.donor_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_donation_form_requires_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.url)

    def test_recording_one_unit_updates_inventory_and_donor_history(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            self.url,
            {
                "registration": self.registration.pk,
                "units_collected": 1,
            },
        )

        self.assertRedirects(response, reverse("camp-manage"))

        self.assertEqual(CampDonation.objects.count(), 1)
        self.assertEqual(BloodUnit.objects.count(), 1)

        donation = CampDonation.objects.get()
        self.assertEqual(donation.units_collected, 1)
        self.assertEqual(donation.recorded_by, self.staff)

        blood_unit = BloodUnit.objects.get()
        self.assertEqual(blood_unit.blood_group, "O+")
        self.assertEqual(blood_unit.quantity, 1)
        self.assertEqual(blood_unit.bank_location, self.camp.venue)
        self.assertEqual(blood_unit.created_by, self.staff)

        history = DonationRecord.objects.get()
        self.assertEqual(history.donor, self.donor)
        self.assertEqual(history.units, 1)
        self.assertEqual(history.donation_date, timezone.localdate())
        self.assertEqual(self.donor.__class__.objects.get(pk=self.donor.pk).last_donation_date,
                         timezone.localdate())

    def test_recording_two_units_creates_two_inventory_entries(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            self.url,
            {
                "registration": self.registration.pk,
                "units_collected": 2,
            },
        )

        self.assertRedirects(response, reverse("camp-manage"))

        self.assertEqual(CampDonation.objects.count(), 1)
        self.assertEqual(BloodUnit.objects.count(), 2)

        history = DonationRecord.objects.get()
        self.assertEqual(history.units, 2)

    def test_duplicate_donation_is_rejected(self):
        self.client.force_login(self.staff)

        payload = {
            "registration": self.registration.pk,
            "units_collected": 1,
        }

        self.client.post(self.url, payload)
        self.client.post(self.url, payload)

        self.assertEqual(CampDonation.objects.count(), 1)
        self.assertEqual(DonationRecord.objects.count(), 1)
        self.assertEqual(BloodUnit.objects.count(), 1)

    def test_invalid_unit_count_is_rejected(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            self.url,
            {
                "registration": self.registration.pk,
                "units_collected": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(CampDonation.objects.count(), 0)
        self.assertEqual(DonationRecord.objects.count(), 0)
        self.assertEqual(BloodUnit.objects.count(), 0)
