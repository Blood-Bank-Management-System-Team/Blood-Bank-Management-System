"""Donor eligibility rules (FR6, FR7, BR-2).

Pure functions: all limits are read from Django settings at call time so
administrators can change them without code changes (BR-3).
"""
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.conf import settings
from django.utils import timezone

HEALTH_FLAG_REASONS = {
    "has_chronic_illness": "Has a chronic illness.",
    "on_medication": "Is currently on medication.",
    "recent_surgery_or_tattoo_6_months": "Had surgery or a tattoo in the last 6 months.",
    "recent_illness_or_fever_2_weeks": "Had an illness or fever in the last 2 weeks.",
    "is_pregnant_or_breastfeeding": "Is pregnant or breastfeeding.",
}


@dataclass
class EligibilityResult:
    eligible: bool
    reasons: list = field(default_factory=list)
    next_eligible_date: date = None


def calculate_age(date_of_birth, today):
    years = today.year - date_of_birth.year
    if (today.month, today.day) < (date_of_birth.month, date_of_birth.day):
        years -= 1
    return years


def next_eligible_date(last_donation_date, today=None):
    """Last donation plus the configured interval, or today if never donated / already passed."""
    today = today or timezone.localdate()
    if last_donation_date is None:
        return today
    candidate = last_donation_date + timedelta(days=settings.BBMS_MIN_DONATION_INTERVAL_DAYS)
    return max(candidate, today)


def check_eligibility(profile, today=None):
    """Evaluate a donor profile (any object with the DonorProfile attributes)."""
    today = today or timezone.localdate()
    reasons = []

    age = calculate_age(profile.date_of_birth, today)
    min_age, max_age = settings.BBMS_MIN_DONOR_AGE, settings.BBMS_MAX_DONOR_AGE
    if age < min_age:
        reasons.append(f"Must be at least {min_age} years old (current age {age}).")
    elif age > max_age:
        reasons.append(f"Must be at most {max_age} years old (current age {age}).")

    min_weight = settings.BBMS_MIN_DONOR_WEIGHT_KG
    if profile.weight_kg < min_weight:
        reasons.append(f"Weight must be at least {min_weight} kg (current weight {profile.weight_kg} kg).")

    for attr, reason in HEALTH_FLAG_REASONS.items():
        if getattr(profile, attr):
            reasons.append(reason)

    next_date = next_eligible_date(profile.last_donation_date, today)
    if next_date > today:
        interval = settings.BBMS_MIN_DONATION_INTERVAL_DAYS
        reasons.append(
            f"Must wait at least {interval} days between donations; next eligible on {next_date.isoformat()}."
        )

    return EligibilityResult(eligible=not reasons, reasons=reasons, next_eligible_date=next_date)
