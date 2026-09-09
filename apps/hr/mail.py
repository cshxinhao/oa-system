"""Email notifications for the leave workflow (synchronous, best-effort)."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse

from .models import LeaveApplication

logger = logging.getLogger(__name__)


def _site_link(path: str) -> str:
    return settings.SITE_URL.rstrip("/") + path


def _leave_list_url() -> str:
    return _site_link(reverse("hr:leave_list"))


def _format_duration(days) -> str:
    if days == 1:
        return "1 day"
    if days == 0.5:
        return "0.5 day (half day)"
    return f"{days} days"


def _format_dates(leave: LeaveApplication) -> str:
    if leave.is_half_day:
        period = leave.get_half_day_period_display() or "AM/PM"
        return f"{leave.start_date} ({period}, half day)"
    if leave.dates.exists():
        return ", ".join(d.date.isoformat() for d in leave.dates.all())
    if leave.start_date == leave.end_date:
        return str(leave.start_date)
    return f"{leave.start_date} to {leave.end_date}"


def notify_approver_of_pending_leave(leave: LeaveApplication) -> None:
    approver = leave.approver
    if approver is None or not approver.email:
        return
    applicant_name = leave.applicant.get_full_name() or leave.applicant.username
    approver_name = approver.get_full_name() or approver.username
    subject = f"[OA] Leave request from {applicant_name} - {leave.get_leave_type_display()}"
    body = (
        f"Dear {approver_name},\n\n"
        f"{applicant_name} has submitted a leave application and selected you "
        f"as the approver.\n\n"
        f"Leave type: {leave.get_leave_type_display()}\n"
        f"Dates: {_format_dates(leave)}\n"
        f"Duration: {_format_duration(leave.duration_days)}\n"
        f"Reason: {leave.reason}\n\n"
        f"Please review the application in the OA system:\n{_leave_list_url()}\n\n"
        f"This is an automated notification from the OA system."
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [approver.email], fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send pending-leave notification to approver #%s (leave #%s)",
            approver.pk, leave.pk)


def notify_applicant_of_outcome(leave: LeaveApplication) -> None:
    applicant = leave.applicant
    if not applicant.email:
        return
    applicant_name = applicant.get_full_name() or applicant.username
    reviewer = leave.reviewer
    reviewer_name = (reviewer.get_full_name() or reviewer.username) if reviewer else "the OA system"
    outcome = "approved" if leave.status == LeaveApplication.STATUS_APPROVED else "rejected"
    subject = f"[OA] Your leave request was {outcome} - {leave.get_leave_type_display()}"
    body = (
        f"Dear {applicant_name},\n\n"
        f"Your leave application has been {outcome}.\n\n"
        f"Leave type: {leave.get_leave_type_display()}\n"
        f"Dates: {_format_dates(leave)}\n"
        f"Duration: {_format_duration(leave.duration_days)}\n"
        f"Reviewed by: {reviewer_name}\n\n"
        f"View your applications in the OA system:\n{_leave_list_url()}\n\n"
        f"This is an automated notification from the OA system."
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [applicant.email], fail_silently=False)
    except Exception:
        logger.exception(
            "Failed to send leave-outcome notification to applicant #%s (leave #%s)",
            applicant.pk, leave.pk)
