import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import NotificationDeliveryLog

logger = logging.getLogger(__name__)


def log_delivery(
    recipient,
    channel,
    notification_type,
    status,
    error_message="",
):
    """Persist the result of a notification delivery attempt."""
    return NotificationDeliveryLog.objects.create(
        recipient=recipient,
        channel=channel,
        notification_type=notification_type,
        status=status,
        error_message=error_message,
    )


def send_notification(
    recipient,
    message,
    notification_type,
    subject="Blood Bank Management System Notification",
    channel="EMAIL",
):
    """Send an email or record an unavailable SMS gateway."""
    if channel == NotificationDeliveryLog.Channel.SMS:
        log_delivery(
            recipient=recipient,
            channel=channel,
            notification_type=notification_type,
            status=NotificationDeliveryLog.Status.FAILED,
            error_message="SMS gateway is not configured.",
        )
        return False

    if channel != NotificationDeliveryLog.Channel.EMAIL:
        raise ValueError(f"Unsupported notification channel: {channel}")

    try:
        sent_count = send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[recipient],
            fail_silently=False,
        )

        if sent_count == 1:
            log_delivery(
                recipient=recipient,
                channel=channel,
                notification_type=notification_type,
                status=NotificationDeliveryLog.Status.SENT,
            )
            return True

        log_delivery(
            recipient=recipient,
            channel=channel,
            notification_type=notification_type,
            status=NotificationDeliveryLog.Status.FAILED,
            error_message="Email backend did not confirm delivery.",
        )
        return False

    except Exception as exc:
        logger.exception("Notification delivery failed.")
        log_delivery(
            recipient=recipient,
            channel=channel,
            notification_type=notification_type,
            status=NotificationDeliveryLog.Status.FAILED,
            error_message=str(exc)[:2000],
        )
        return False


def notify_eligibility(donor):
    """Notify a donor about their current eligibility status."""
    eligibility = donor.eligibility()

    if eligibility.eligible:
        message = (
            "Your donor profile currently meets the blood donation "
            "eligibility rules. Please contact your blood bank before "
            "donating."
        )
    else:
        reasons = "\n".join(f"- {reason}" for reason in eligibility.reasons)
        message = (
            "Your donor profile is currently not eligible to donate.\n\n"
            f"{reasons}\n\n"
            f"Next eligible date: {eligibility.next_eligible_date}"
        )

    email = donor.user.email
    if not email:
        log_delivery(
            recipient=f"user:{donor.user_id}",
            channel=NotificationDeliveryLog.Channel.EMAIL,
            notification_type=NotificationDeliveryLog.NotificationType.ELIGIBILITY,
            status=NotificationDeliveryLog.Status.FAILED,
            error_message="Donor does not have an email address.",
        )
        return False

    return send_notification(
        recipient=email,
        subject="Blood Donation Eligibility Update",
        message=message,
        notification_type=NotificationDeliveryLog.NotificationType.ELIGIBILITY,
    )


def notify_camp(donor, camp_name, camp_details=""):
    """Send a blood donation camp announcement to a donor."""
    message = f"Blood donation camp: {camp_name}\n\n{camp_details}".strip()
    return _send_donor_email(
        donor,
        message,
        NotificationDeliveryLog.NotificationType.CAMP,
        "Blood Donation Camp Announcement",
    )


def notify_request_status(recipient_email, request_reference, status, details=""):
    """Notify a requester about a blood request status change."""
    message = (
        f"Blood request {request_reference} status has changed to: {status}.\n\n"
        f"{details}"
    ).strip()
    return send_notification(
        recipient=recipient_email,
        subject="Blood Request Status Update",
        message=message,
        notification_type=NotificationDeliveryLog.NotificationType.REQUEST_STATUS,
    )


def notify_urgent_need(recipient_email, blood_group, city, details=""):
    """Notify a recipient about an urgent blood requirement."""
    message = (
        f"Urgent blood requirement: {blood_group}\n"
        f"Location: {city}\n\n{details}"
    ).strip()
    return send_notification(
        recipient=recipient_email,
        subject="Urgent Blood Requirement",
        message=message,
        notification_type=NotificationDeliveryLog.NotificationType.URGENT_NEED,
    )


def _send_donor_email(donor, message, notification_type, subject):
    email = donor.user.email
    if not email:
        log_delivery(
            recipient=f"user:{donor.user_id}",
            channel=NotificationDeliveryLog.Channel.EMAIL,
            notification_type=notification_type,
            status=NotificationDeliveryLog.Status.FAILED,
            error_message="Donor does not have an email address.",
        )
        return False

    return send_notification(
        recipient=email,
        subject=subject,
        message=message,
        notification_type=notification_type,
    )


def emergency_broadcast(blood_group, city, details=""):
    """
    Notify eligible donors in a city who match the requested blood group.

    Returns a summary of attempted deliveries. Email delivery is attempted
    only for donors with a usable email address.
    """
    from donors.models import DonorProfile

    donors = DonorProfile.objects.filter(
        blood_group=blood_group,
        city__iexact=city,
        user__role="DONOR",
    ).select_related("user")

    summary = {
        "blood_group": blood_group,
        "city": city,
        "matched_donors": 0,
        "eligible_donors": 0,
        "sent": 0,
        "failed": 0,
        "skipped_ineligible": 0,
    }

    for donor in donors:
        summary["matched_donors"] += 1

        if not donor.eligibility().eligible:
            summary["skipped_ineligible"] += 1
            continue

        summary["eligible_donors"] += 1

        message = (
            "EMERGENCY BLOOD DONOR REQUEST\n\n"
            f"Blood group needed: {blood_group}\n"
            f"Location: {city}\n\n"
            f"{details}\n\n"
            "If you are available, please contact the requesting blood bank. "
            "This notification is not a guarantee that donation is medically "
            "appropriate; follow blood bank screening guidance."
        ).strip()

        if not donor.user.email:
            log_delivery(
                recipient=f"user:{donor.user_id}",
                channel=NotificationDeliveryLog.Channel.EMAIL,
                notification_type=NotificationDeliveryLog.NotificationType.EMERGENCY,
                status=NotificationDeliveryLog.Status.FAILED,
                error_message="Donor does not have an email address.",
            )
            summary["failed"] += 1
            continue

        sent = send_notification(
            recipient=donor.user.email,
            subject="Emergency Blood Donation Request",
            message=message,
            notification_type=NotificationDeliveryLog.NotificationType.EMERGENCY,
)

        if sent:
            summary["sent"] += 1
        else:
            summary["failed"] += 1

    return summary
