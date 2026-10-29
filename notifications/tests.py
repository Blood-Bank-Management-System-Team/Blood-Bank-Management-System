from datetime import date, timedelta
from unittest.mock import patch

from django.test import override_settings
from donors.models import DonorProfile
from notifications.models import NotificationDeliveryLog

from django.utils import timezone
from rest_framework.test import APITestCase

from inventory.models import BloodUnit
from users.models import User
from .models import AdminNotification, LowStockThreshold


class LowStockAlertsTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="test_admin",
            email="admin@example.com",
            password="TestAdmin@12345",
        )
        self.url = "/api/notifications/low-stock/"

        LowStockThreshold.objects.create(
            blood_group="O+",
            minimum_quantity=5,
        )

    def test_alert_is_returned_when_stock_is_below_threshold(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["blood_group"], "O+")
        self.assertEqual(response.data[0]["available_quantity"], 0)
        self.assertEqual(response.data[0]["minimum_quantity"], 5)

    def test_alert_is_not_returned_when_stock_meets_threshold(self):
        BloodUnit.objects.create(
            blood_group="O+",
            quantity=5,
            collection_date=timezone.localdate(),
            expiry_date=timezone.localdate() + timezone.timedelta(days=30),
            bank_location="Test Blood Bank",
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    def test_non_admin_cannot_view_alerts(self):
        donor = User.objects.create_user(
            username="test_donor",
            password="TestDonor@12345",
            role=User.Role.DONOR,
        )
        self.client.force_authenticate(user=donor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_low_stock_creates_admin_notification(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(AdminNotification.objects.count(), 1)

        notification = AdminNotification.objects.get()
        self.assertEqual(notification.blood_group, "O+")
        self.assertEqual(notification.available_quantity, 0)
        self.assertEqual(notification.minimum_quantity, 5)
        self.assertFalse(notification.is_read)

    def test_repeated_requests_do_not_duplicate_unread_notifications(self):
        self.client.force_authenticate(user=self.admin)

        self.client.get(self.url)
        self.client.get(self.url)

        self.assertEqual(
            AdminNotification.objects.filter(
                blood_group="O+",
                is_read=False,
            ).count(),
            1,
        )

    def test_existing_unread_notification_is_updated(self):
        notification = AdminNotification.objects.create(
            blood_group="O+",
            message="Low stock for O+: 2 available, minimum is 5.",
            available_quantity=2,
            minimum_quantity=5,
        )

        BloodUnit.objects.create(
            blood_group="O+",
            quantity=3,
            collection_date=timezone.localdate(),
            expiry_date=timezone.localdate() + timezone.timedelta(days=30),
            bank_location="Test Blood Bank",
        )

        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        notification.refresh_from_db()
        self.assertEqual(notification.available_quantity, 3)
        self.assertEqual(notification.minimum_quantity, 5)
        self.assertEqual(AdminNotification.objects.count(), 1)

class EmergencyBroadcastTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="broadcast_admin",
            email="admin@example.com",
            password="AdminTest@12345",
            role=User.Role.ADMIN,
        )
        self.donor_user = User.objects.create_user(
            username="eligible_donor",
            email="donor@example.com",
            password="DonorTest@12345",
            role=User.Role.DONOR,
        )
        self.url = "/api/notifications/emergency-broadcast/"

        DonorProfile.objects.create(
            user=self.donor_user,
            blood_group="O+",
            date_of_birth=date.today() - timedelta(days=30 * 365),
            weight_kg=65,
            gender="MALE",
            address="Test Address",
            city="Bidar",
        )

        self.payload = {
            "blood_group": "O+",
            "city": "Bidar",
            "details": "Urgent blood requirement.",
        }

    def test_admin_can_trigger_emergency_broadcast(self):
        self.client.force_authenticate(user=self.admin)

        with patch(
            "notifications.services.send_mail",
            return_value=1,
        ):
            response = self.client.post(
                self.url,
                self.payload,
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["matched_donors"], 1)
        self.assertEqual(response.data["eligible_donors"], 1)
        self.assertEqual(response.data["sent"], 1)
        self.assertEqual(response.data["failed"], 0)

        log = NotificationDeliveryLog.objects.get()
        self.assertEqual(log.status, NotificationDeliveryLog.Status.SENT)
        self.assertEqual(
            log.notification_type,
            NotificationDeliveryLog.NotificationType.EMERGENCY,
        )

    def test_donor_cannot_trigger_emergency_broadcast(self):
        self.client.force_authenticate(user=self.donor_user)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_trigger_broadcast(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_ineligible_donor_is_skipped(self):
        donor = DonorProfile.objects.get(user=self.donor_user)
        donor.has_chronic_illness = True
        donor.save(update_fields=["has_chronic_illness"])

        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["matched_donors"], 1)
        self.assertEqual(response.data["eligible_donors"], 0)
        self.assertEqual(response.data["skipped_ineligible"], 1)
        self.assertEqual(response.data["sent"], 0)
        self.assertEqual(NotificationDeliveryLog.objects.count(), 0)

    def test_email_failure_is_logged_and_counted(self):
        self.client.force_authenticate(user=self.admin)

        with patch(
            "notifications.services.send_mail",
            side_effect=RuntimeError("Test email failure"),
        ):
            response = self.client.post(
                self.url,
                self.payload,
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["sent"], 0)
        self.assertEqual(response.data["failed"], 1)

        log = NotificationDeliveryLog.objects.get()
        self.assertEqual(log.status, NotificationDeliveryLog.Status.FAILED)
        self.assertIn("Test email failure", log.error_message)

    def test_invalid_blood_group_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            **self.payload,
            "blood_group": "INVALID",
        }
        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_empty_city_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            **self.payload,
            "city": "   ",
        }
        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_donor_in_another_city_is_not_notified(self):
        donor = DonorProfile.objects.get(user=self.donor_user)
        donor.city = "Kalaburagi"
        donor.save(update_fields=["city"])

        self.client.force_authenticate(user=self.admin)

        with patch(
            "notifications.services.send_mail",
            return_value=1,
        ) as mocked_send_mail:
            response = self.client.post(
                self.url,
                self.payload,
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["matched_donors"], 0)
        self.assertEqual(response.data["sent"], 0)
        mocked_send_mail.assert_not_called()