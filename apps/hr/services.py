from datetime import date, timedelta
from decimal import Decimal

from .models import LeaveApplication, LeaveQuota


def is_weekend(d):
    return d.weekday() >= 5


def count_working_days(start, end):
    """Number of Mon-Fri days in the inclusive range [start, end]."""
    days = (end - start).days + 1
    if days <= 0:
        return 0
    full_weeks, remainder = divmod(days, 7)
    working = full_weeks * 5
    for i in range(remainder):
        if (start + timedelta(days=i)).weekday() < 5:
            working += 1
    return working


def requested_duration(cleaned_data):
    """Working days requested from form cleaned data (weekends excluded for annual leave):
    half-day 0.5; parsed_dates count; else range."""
    if cleaned_data.get('is_half_day'):
        return Decimal('0.5')
    parsed = cleaned_data.get('parsed_dates')
    if parsed:
        return Decimal(sum(1 for d in parsed if not is_weekend(d)))
    start = cleaned_data.get('start_date')
    end = cleaned_data.get('end_date')
    if not start or not end:
        return Decimal('0')
    return Decimal(count_working_days(start, end))


def leave_used_days(user, year, leave_type):
    """Sum of working days (weekends excluded) of APPROVED leave applications of
    `leave_type` falling inside `year`."""
    total = Decimal('0.0')
    applications = (
        LeaveApplication.objects.filter(
            applicant=user,
            leave_type=leave_type,
            status=LeaveApplication.STATUS_APPROVED,
        ).prefetch_related('dates')
    )
    for application in applications:
        if application.is_half_day:
            # half-day leave is validated to a single day
            if application.start_date.year == year:
                total += Decimal('0.5')
            continue
        dates = list(application.dates.all())
        if dates:
            # discontinuous dates: count per date
            for d in dates:
                if d.date.year == year and not is_weekend(d.date):
                    total += Decimal('1')
            continue
        # contiguous range: overlap with the year
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        low = max(application.start_date, year_start)
        high = min(application.end_date, year_end)
        if low <= high:
            total += Decimal(count_working_days(low, high))
    return total


def annual_leave_used_days(user, year):
    """Backwards-compatible wrapper for the annual leave type."""
    return leave_used_days(user, year, LeaveApplication.TYPE_ANNUAL)


def quota_summary(user, year=None, leave_type=LeaveApplication.TYPE_ANNUAL):
    """Return {leave_type, year, total, used, remaining} for one quota of the user,
    or None if not configured."""
    if year is None:
        year = date.today().year
    try:
        quota = LeaveQuota.objects.get(user=user, year=year, leave_type=leave_type)
    except LeaveQuota.DoesNotExist:
        return None
    used = leave_used_days(user, year, leave_type)
    return {
        'leave_type': leave_type,
        'year': year,
        'total': quota.total_days,
        'used': used,
        'remaining': quota.total_days - used,
    }


def quota_summaries(user):
    """Return a list of {leave_type, leave_type_display, year, total, used, remaining}
    for all quotas of the user, most recent year first — used by the Leave Quota tab."""
    type_display = dict(LeaveApplication.TYPE_CHOICES)
    summaries = []
    for quota in LeaveQuota.objects.filter(user=user).order_by('-year', 'leave_type'):
        used = leave_used_days(user, quota.year, quota.leave_type)
        summaries.append({
            'leave_type': quota.leave_type,
            'leave_type_display': type_display.get(quota.leave_type, quota.leave_type),
            'year': quota.year,
            'total': quota.total_days,
            'used': used,
            'remaining': quota.total_days - used,
        })
    return summaries
