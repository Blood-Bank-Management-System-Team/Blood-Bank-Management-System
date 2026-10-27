"""Aggregation queries behind the BB-17 reports dashboard, API and CSV export.

Every function takes an inclusive ``date_from`` / ``date_to`` and uses database
aggregation only (no Python loops over model rows).
"""
from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db.models import Case, CharField, Count, F, Q, Sum, Value, When
from django.db.models.functions import TruncDate
from django.utils import timezone

from bloodrequests.models import BloodRequest
from donors.models import DonationRecord
from inventory.models import BloodStock
from notifications.models import LowStockThreshold

DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 366
BLOOD_GROUPS = BloodStock.BloodGroup.values
WASTAGE_REASONS = ("expired", "other")


def parse_date_range(params):
    """Read ``date_from`` / ``date_to`` (YYYY-MM-DD); default is the last 30 days.

    Raises django ValidationError with a message dict on bad input.
    """
    today = timezone.localdate()
    values, errors = {}, {}
    for key in ("date_from", "date_to"):
        raw = (params.get(key) or "").strip()
        if not raw:
            continue
        try:
            values[key] = date.fromisoformat(raw)
        except ValueError:
            errors[key] = "Invalid date. Use the format YYYY-MM-DD."
    if errors:
        raise ValidationError(errors)
    date_to = values.get("date_to", today)
    date_from = values.get("date_from", date_to - timedelta(days=DEFAULT_RANGE_DAYS))
    if date_from > date_to:
        raise ValidationError({"date_from": "date_from must not be after date_to."})
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        raise ValidationError({"date_from": f"Date range must not exceed {MAX_RANGE_DAYS} days."})
    return date_from, date_to


def donations_report(date_from, date_to):
    qs = DonationRecord.objects.filter(donation_date__range=(date_from, date_to))
    totals = qs.aggregate(total_units=Sum("units"), total_donations=Count("id"))
    per_day = {
        row["donation_date"]: row
        for row in qs.values("donation_date").annotate(units=Sum("units"), donations=Count("id"))
    }
    daily = []
    for offset in range((date_to - date_from).days + 1):  # one entry per calendar day, zero-filled
        day = date_from + timedelta(days=offset)
        row = per_day.get(day)
        daily.append({
            "date": day.isoformat(),
            "units": row["units"] if row else 0,
            "donations": row["donations"] if row else 0,
        })
    return {
        "total_units": totals["total_units"] or 0,
        "total_donations": totals["total_donations"],
        "daily": daily,
    }


def stock_report():
    """Units currently available per blood group (a snapshot: the range does not apply)."""
    today = timezone.localdate()
    available = dict(
        BloodStock.objects.filter(
            status=BloodStock.StockStatus.AVAILABLE, expiry_date__gte=today
        ).values_list("blood_group").annotate(total=Sum("available_units"))
    )
    thresholds = dict(LowStockThreshold.objects.values_list("blood_group", "minimum_quantity"))
    groups, low_stock = [], []
    for group in BLOOD_GROUPS:
        units = available.get(group) or 0
        minimum = thresholds.get(group)
        is_low = minimum is not None and units < minimum
        groups.append({"blood_group": group, "units": units, "minimum": minimum, "low_stock": is_low})
        if is_low:
            low_stock.append(group)
    return {
        "total_units": sum(g["units"] for g in groups),
        "groups": groups,
        "low_stock_groups": low_stock,
    }


def requests_report(date_from, date_to):
    qs = BloodRequest.objects.filter(created_at__date__range=(date_from, date_to))
    counts = qs.aggregate(
        total=Count("id"),
        **{s: Count("id", filter=Q(status=s)) for s in BloodRequest.RequestStatus.values},
        **{f"p_{p}": Count("id", filter=Q(priority=p)) for p in BloodRequest.Priority.values},
    )
    return {
        "total": counts["total"],
        "by_status": {s: counts[s] for s in BloodRequest.RequestStatus.values},
        "by_priority": {p: counts[f"p_{p}"] for p in BloodRequest.Priority.values},
    }


def wastage_report(date_from, date_to):
    """Disposed stock whose disposal (last update) falls in the range.

    The inventory app records disposal as ``status=DISPOSED`` without a reason
    field, so the reason is derived: ``expired`` when the batch had passed its
    expiry date when it was disposed, otherwise ``other`` (e.g. damaged).
    """
    qs = BloodStock.objects.filter(
        status=BloodStock.StockStatus.DISPOSED,
        updated_at__date__range=(date_from, date_to),
    ).annotate(
        disposed_on=TruncDate("updated_at"),
        reason=Case(
            When(expiry_date__lte=F("disposed_on"), then=Value("expired")),
            default=Value("other"),
            output_field=CharField(),
        ),
    )
    by_group = dict(qs.values_list("blood_group").annotate(total=Sum("available_units")))
    by_reason = dict(qs.values_list("reason").annotate(total=Sum("available_units")))
    return {
        "total_units": sum(by_group.values()),
        "by_blood_group": {g: by_group.get(g, 0) for g in BLOOD_GROUPS},
        "by_reason": {r: by_reason.get(r, 0) for r in WASTAGE_REASONS},
    }


def build_summary(date_from, date_to):
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "donations": donations_report(date_from, date_to),
        "stock": stock_report(),
        "requests": requests_report(date_from, date_to),
        "wastage": wastage_report(date_from, date_to),
    }
