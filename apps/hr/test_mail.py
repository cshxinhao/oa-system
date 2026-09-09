from datetime import date
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Department, User
from hr.mail import notify_approver_of_pending_leave
from hr.models import LeaveApplication, LeaveApplicationDate


class LeaveEmailTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="R&D")
        self.manager = User.objects.create_user(
            username="manager",
            password="pwd",
            email="manager@example.com",
            department=self.department,
        )
        self.department.manager = self.manager
        self.department.save()
        self.employee = User.objects.create_user(
            username="employee",
            password="pwd",
            email="employee@example.com",
            department=self.department,
        )

    def leave_data(self, **overrides):
        # 2026-02-16 (Mon) and 2026-02-17 (Tue) are working days
        data = {
            "leave_type": "sick",
            "start_date": "2026-02-16",
            "end_date": "2026-02-17",
            "approver": self.manager.pk,
            "reason": "Feeling unwell",
        }
        data.update(overrides)
        return data

    def submit_leave(self, **overrides):
        self.client.force_login(self.employee)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse("hr:leave_create"), data=self.leave_data(**overrides)
            )

    def _create_pending_leave(self):
        leave = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="sick",
            start_date=date(2026, 2, 16),
            end_date=date(2026, 2, 17),
            reason="Feeling unwell",
            approver=self.manager,
        )
        leave.submit()
        leave.save()
        return leave

    @override_settings(SITE_URL="http://example.test")
    def test_submit_notifies_selected_approver(self):
        resp = self.submit_leave()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.manager.email])
        self.assertIn("employee", message.body)
        self.assertIn("Sick Leave", message.body)
        self.assertIn("2026-02-16 to 2026-02-17", message.body)
        self.assertIn("2 days", message.body)
        self.assertIn("Feeling unwell", message.body)
        self.assertIn("http://example.test/hr/leaves/", message.body)

    def test_approve_notifies_applicant(self):
        leave = self._create_pending_leave()
        self.client.force_login(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(reverse("hr:leave_approve", args=[leave.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.employee.email])
        self.assertIn("has been approved", message.body)
        self.assertIn("Reviewed by: manager", message.body)

    def test_reject_notifies_applicant(self):
        leave = self._create_pending_leave()
        self.client.force_login(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(reverse("hr:leave_reject", args=[leave.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.employee.email])
        self.assertIn("has been rejected", message.body)
        self.assertIn("Reviewed by: manager", message.body)

    def test_half_day_email_mentions_period(self):
        resp = self.submit_leave(
            start_date="2026-02-16",
            end_date="2026-02-16",
            is_half_day="on",
            half_day_period="am",
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("2026-02-16 (AM, half day)", body)
        self.assertIn("0.5 day (half day)", body)

    def test_discontinuous_dates_listed_in_email(self):
        leave = self._create_pending_leave()
        LeaveApplicationDate.objects.create(application=leave, date=date(2026, 2, 16))
        LeaveApplicationDate.objects.create(application=leave, date=date(2026, 2, 18))
        notify_approver_of_pending_leave(leave)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("2026-02-16, 2026-02-18", mail.outbox[0].body)

    def test_no_email_when_recipient_has_no_address(self):
        self.manager.email = ""
        self.manager.save()
        resp = self.submit_leave()
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(LeaveApplication.objects.filter(applicant=self.employee).exists())
        self.assertEqual(len(mail.outbox), 0)

    @patch("hr.mail.send_mail", side_effect=Exception("smtp down"))
    def test_smtp_failure_does_not_break_submit_or_approve(self, mock_send):
        with self.assertLogs("hr.mail", level="ERROR"):
            resp = self.submit_leave()
        self.assertEqual(resp.status_code, 302)
        leave = LeaveApplication.objects.get(applicant=self.employee)
        self.assertEqual(leave.status, LeaveApplication.STATUS_PENDING)

        self.client.force_login(self.manager)
        with self.assertLogs("hr.mail", level="ERROR"):
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.client.post(reverse("hr:leave_approve", args=[leave.pk]))
        self.assertEqual(resp.status_code, 302)
        # FSMField is protected — re-fetch instead of refresh_from_db()
        leave = LeaveApplication.objects.get(pk=leave.pk)
        self.assertEqual(leave.status, LeaveApplication.STATUS_APPROVED)

    def test_second_approval_attempt_sends_no_email(self):
        leave = self._create_pending_leave()
        self.client.force_login(self.manager)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(reverse("hr:leave_approve", args=[leave.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

        # application is no longer pending — the view bails out before
        # registering an on_commit callback, so no second email goes out
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(reverse("hr:leave_approve", args=[leave.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
