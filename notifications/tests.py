
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
