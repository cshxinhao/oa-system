from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from core.models import Department, User
from hr.models import LeaveApplication, LeaveApplicationDate, LeaveQuota
from hr.permissions import can_approve_application, get_pending_leaves_for_approver
from hr.services import annual_leave_used_days


class LeaveFlowTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="研发部")
        self.manager = User.objects.create_user(
            username="manager",
            password="pwd",
            department=self.department,
        )
        self.department.manager = self.manager
        self.department.save()
        self.employee = User.objects.create_user(
            username="employee",
            password="pwd",
            department=self.department,
        )

    def leave_data(self, **overrides):
        data = {
            "leave_type": "sick",
            "start_date": "2026-02-14",
            "end_date": "2026-02-15",
            "approver": self.manager.pk,
            "reason": "身体不适",
        }
        data.update(overrides)
        return data

    def submit_leave(self, client=None, **overrides):
        client = client or self.client
        return client.post(reverse("hr:leave_create"), data=self.leave_data(**overrides))

    # ---------- existing flows ----------

    def test_submit_leave_redirect_and_list_shows_approver(self):
        self.client.force_login(self.employee)
        resp = self.client.post(reverse("hr:leave_create"), data=self.leave_data(), follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Leave application submitted")
        application = LeaveApplication.objects.get(applicant=self.employee)
        self.assertEqual(application.approver, self.manager)
        self.assertIsNone(application.reviewer)
        self.assertEqual(application.status, LeaveApplication.STATUS_PENDING)

    def test_date_range_validation(self):
        self.client.force_login(self.employee)
        resp = self.submit_leave(start_date="2026-02-16", end_date="2026-02-15", reason="日期填错")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "End date cannot be earlier than start date")
        self.assertEqual(LeaveApplication.objects.filter(applicant=self.employee).count(), 0)

    def test_manager_can_see_tab_and_approve_own_department(self):
        leave = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="sick",
            start_date=date(2026, 2, 14),
            end_date=date(2026, 2, 15),
            reason="测试审批",
            approver=self.manager,
        )
        leave.submit()
        leave.save()

        self.client.force_login(self.manager)
        resp = self.client.get(reverse("hr:leave_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "测试审批")

        resp2 = self.client.post(reverse("hr:leave_approve", args=[leave.pk]), follow=True)
        self.assertEqual(resp2.status_code, 200)
        leave = LeaveApplication.objects.get(pk=leave.pk)
        self.assertEqual(leave.status, LeaveApplication.STATUS_APPROVED)
        self.assertEqual(leave.approver, self.manager)
        self.assertEqual(leave.reviewer, self.manager)

    def test_dashboard_shows_leave_approval_for_approver(self):
        leave = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="sick",
            start_date=date(2026, 2, 14),
            end_date=date(2026, 2, 15),
            reason="仪表盘审批",
            approver=self.manager,
        )
        leave.submit()
        leave.save()

        self.client.force_login(self.manager)
        resp = self.client.get(reverse("index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "仪表盘审批")
        self.assertContains(resp, reverse("hr:leave_approve", args=[leave.pk]))

    # ---------- approver picker ----------

    def test_approver_picker_preselected_org_candidate(self):
        self.client.force_login(self.employee)
        resp = self.client.get(reverse("hr:leave_create"))
        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        self.assertEqual(form.fields["approver"].initial, self.manager.pk)
        self.assertIn(self.manager.pk, set(form.fields["approver"].queryset.values_list("pk", flat=True)))

    def test_global_approver_in_picker_for_no_department_employee(self):
        global_approver = User.objects.create_user(
            username="global_approver", password="pwd", can_approve_all_leaves=True
        )
        employee_no_dept = User.objects.create_user(username="no_dept", password="pwd")

        self.client.force_login(employee_no_dept)
        resp = self.client.get(reverse("hr:leave_create"))
        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        self.assertIn(global_approver.pk, set(form.fields["approver"].queryset.values_list("pk", flat=True)))

        resp2 = self.submit_leave(client=self.client, approver=global_approver.pk, reason="无部门测试")
        self.assertEqual(resp2.status_code, 302)
        application = LeaveApplication.objects.get(applicant=employee_no_dept)
        self.assertEqual(application.approver, global_approver)

    def test_tampered_approver_rejected(self):
        outsider = User.objects.create_user(username="outsider", password="pwd")
        self.client.force_login(self.employee)
        resp = self.submit_leave(approver=outsider.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "The selected approver is not eligible to approve this application")
        self.assertEqual(LeaveApplication.objects.filter(applicant=self.employee).count(), 0)

    def test_empty_eligible_approver_list_blocks_submit(self):
        employee_no_dept = User.objects.create_user(username="no_dept2", password="pwd")
        self.client.force_login(employee_no_dept)
        resp = self.client.post(
            reverse("hr:leave_create"),
            data={
                "leave_type": "sick",
                "start_date": "2026-02-14",
                "end_date": "2026-02-15",
                "reason": "没有审批人",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No eligible approver is available")
        self.assertEqual(LeaveApplication.objects.filter(applicant=employee_no_dept).count(), 0)

    def test_global_approver_sees_all_pending_and_can_approve(self):
        leave = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="sick",
            start_date=date(2026, 2, 14),
            end_date=date(2026, 2, 15),
            reason="全局审批测试",
            approver=self.manager,
        )
        leave.submit()
        leave.save()

        global_approver = User.objects.create_user(
            username="global_approver2", password="pwd", can_approve_all_leaves=True
        )
        own_leave = LeaveApplication.objects.create(
            applicant=global_approver,
            leave_type="sick",
            start_date=date(2026, 2, 20),
            end_date=date(2026, 2, 20),
            reason="自己的申请",
            approver=self.manager,
        )
        own_leave.submit()
        own_leave.save()

        pending = get_pending_leaves_for_approver(global_approver)
        self.assertIn(leave.pk, set(pending.values_list("pk", flat=True)))
        self.assertNotIn(own_leave.pk, set(pending.values_list("pk", flat=True)))
        self.assertTrue(can_approve_application(global_approver, leave))

        self.client.force_login(global_approver)
        resp = self.client.post(reverse("hr:leave_approve", args=[leave.pk]), follow=True)
        self.assertEqual(resp.status_code, 200)
        leave = LeaveApplication.objects.get(pk=leave.pk)
        self.assertEqual(leave.status, LeaveApplication.STATUS_APPROVED)
        # the selected approver stays unchanged; the reviewer records who actually approved
        self.assertEqual(leave.approver, self.manager)
        self.assertEqual(leave.reviewer, global_approver)
        self.assertTrue(
            LeaveApplication.objects.filter(reviewer=global_approver, pk=leave.pk).exists()
        )

        # the applicant sees both names in their own list
        self.client.force_login(self.employee)
        resp = self.client.get(reverse("hr:leave_list"))
        self.assertContains(resp, "global_approver2")
        self.assertContains(resp, "manager")

    # ---------- annual leave quota ----------

    def test_annual_quota_missing_record_blocks(self):
        self.client.force_login(self.employee)
        resp = self.submit_leave(
            leave_type="annual", start_date="2026-02-01", end_date="2026-02-03", reason="年假测试"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No annual leave quota has been configured")
        self.assertEqual(LeaveApplication.objects.filter(applicant=self.employee).count(), 0)

    def test_annual_quota_hard_block(self):
        LeaveQuota.objects.create(user=self.employee, year=2026, total_days=Decimal("10.0"))
        self.client.force_login(self.employee)

        resp = self.submit_leave(
            leave_type="annual", start_date="2026-03-02", end_date="2026-03-16", reason="超额年假"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Insufficient annual leave balance")
        self.assertEqual(LeaveApplication.objects.filter(applicant=self.employee).count(), 0)

        resp2 = self.submit_leave(
            leave_type="annual", start_date="2026-02-02", end_date="2026-02-06", reason="正常年假"
        )
        self.assertEqual(resp2.status_code, 302)
        self.assertEqual(LeaveApplication.objects.filter(applicant=self.employee).count(), 1)

    def test_quota_used_days_counts_only_approved(self):
        approved_range = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="annual",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 3),
            reason="已批准两天",
            approver=self.manager,
        )
        approved_range.submit()
        approved_range.save()
        approved_range.approve()
        approved_range.save()

        approved_half = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="annual",
            is_half_day=True,
            half_day_period=LeaveApplication.HALF_DAY_AM,
            start_date=date(2026, 3, 4),
            end_date=date(2026, 3, 4),
            reason="已批准半天",
            approver=self.manager,
        )
        approved_half.submit()
        approved_half.save()
        approved_half.approve()
        approved_half.save()

        pending = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="annual",
            start_date=date(2026, 3, 4),
            end_date=date(2026, 3, 5),
            reason="待审批不算",
            approver=self.manager,
        )
        pending.submit()
        pending.save()

        self.assertEqual(annual_leave_used_days(self.employee, 2026), Decimal("2.5"))

    def test_quota_discontinuous_and_year_boundary(self):
        discontinuous = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="annual",
            start_date=date(2026, 12, 28),
            end_date=date(2027, 1, 4),
            reason="不连续跨年",
            approver=self.manager,
        )
        discontinuous.submit()
        discontinuous.save()
        LeaveApplicationDate.objects.create(application=discontinuous, date=date(2026, 12, 28))
        LeaveApplicationDate.objects.create(application=discontinuous, date=date(2027, 1, 4))
        discontinuous.approve()
        discontinuous.save()

        spanning = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="annual",
            start_date=date(2026, 12, 29),
            end_date=date(2027, 1, 3),
            reason="跨年区间",
            approver=self.manager,
        )
        spanning.submit()
        spanning.save()
        spanning.approve()
        spanning.save()

        self.assertEqual(annual_leave_used_days(self.employee, 2026), Decimal("4"))
        # 2027: Jan 1 (Fri) counts, Jan 2-3 (weekend) excluded, plus Jan 4 from the discontinuous leave
        self.assertEqual(annual_leave_used_days(self.employee, 2027), Decimal("2"))

    def test_weekend_excluded_from_annual_usage(self):
        LeaveQuota.objects.create(user=self.employee, year=2026, total_days=Decimal("10.0"))
        self.client.force_login(self.employee)
        # Fri 2026-02-06 to Mon 2026-02-09: 4 calendar days, 2 working days
        resp = self.submit_leave(
            leave_type="annual", start_date="2026-02-06", end_date="2026-02-09", reason="跨周末年假"
        )
        self.assertEqual(resp.status_code, 302)
        application = LeaveApplication.objects.get(applicant=self.employee, leave_type="annual")
        self.assertEqual(application.duration_days, 2)

        self.client.force_login(self.manager)
        self.client.post(reverse("hr:leave_approve", args=[application.pk]), follow=True)
        self.assertEqual(annual_leave_used_days(self.employee, 2026), Decimal("2"))

    def test_weekend_excluded_for_all_leave_types(self):
        self.client.force_login(self.employee)
        # sick leave Fri 2026-02-06 to Mon 2026-02-09: 4 calendar days, 2 working days
        resp = self.submit_leave(
            leave_type="sick", start_date="2026-02-06", end_date="2026-02-09", reason="跨周末病假"
        )
        self.assertEqual(resp.status_code, 302)
        application = LeaveApplication.objects.get(applicant=self.employee, leave_type="sick")
        self.assertEqual(application.duration_days, 2)

    def test_annual_all_weekend_blocked(self):
        LeaveQuota.objects.create(user=self.employee, year=2026, total_days=Decimal("10.0"))
        self.client.force_login(self.employee)
        # Sat 2026-02-07 to Sun 2026-02-08: no working days
        resp = self.submit_leave(
            leave_type="annual", start_date="2026-02-07", end_date="2026-02-08", reason="纯周末"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "The selected dates contain no working days.")
        self.assertEqual(LeaveApplication.objects.filter(applicant=self.employee).count(), 0)

    def test_annual_validation_counts_working_days(self):
        LeaveQuota.objects.create(user=self.employee, year=2026, total_days=Decimal("10.0"))
        self.client.force_login(self.employee)
        # Mon 2026-03-02 to Fri 2026-03-20: 19 calendar days, 15 working days > 10
        resp = self.submit_leave(
            leave_type="annual", start_date="2026-03-02", end_date="2026-03-20", reason="工作日校验"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "requesting 15 days")
        self.assertEqual(LeaveApplication.objects.filter(applicant=self.employee).count(), 0)

    def test_quota_tag_renders(self):
        LeaveQuota.objects.create(user=self.employee, year=2026, total_days=Decimal("10.0"))
        approved_range = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="annual",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 3),
            reason="两天",
            approver=self.manager,
        )
        approved_range.submit()
        approved_range.save()
        approved_range.approve()
        approved_range.save()
        approved_half = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="annual",
            is_half_day=True,
            half_day_period=LeaveApplication.HALF_DAY_PM,
            start_date=date(2026, 3, 4),
            end_date=date(2026, 3, 4),
            reason="半天",
            approver=self.manager,
        )
        approved_half.submit()
        approved_half.save()
        approved_half.approve()
        approved_half.save()

        self.client.force_login(self.employee)
        resp = self.client.get(reverse("hr:leave_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Used 2.5 / 10.0 days")

    def test_leave_quota_tab_renders(self):
        LeaveQuota.objects.create(user=self.employee, year=2026, total_days=Decimal("10.0"))
        LeaveQuota.objects.create(user=self.employee, year=2026, leave_type="sick", total_days=Decimal("5.0"))
        approved = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="annual",
            start_date=date(2026, 3, 2),
            end_date=date(2026, 3, 3),
            reason="两天",
            approver=self.manager,
        )
        approved.submit()
        approved.save()
        approved.approve()
        approved.save()

        self.client.force_login(self.employee)
        resp = self.client.get(reverse("hr:leave_list"))
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        # Leave Quota is the leftmost tab
        self.assertLess(content.index("Leave Quota"), content.index("My Applications"))
        self.assertContains(resp, "Annual Leave")
        self.assertContains(resp, "Sick Leave")
        self.assertContains(resp, "8.0")  # annual remaining = 10 - 2

    def test_pending_tab_shows_applicant_quota(self):
        LeaveQuota.objects.create(user=self.employee, year=2026, total_days=Decimal("10.0"))
        self.client.force_login(self.employee)
        self.submit_leave(reason="看额度")
        self.client.logout()

        self.client.force_login(self.manager)
        resp = self.client.get(reverse("hr:leave_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "0.0/10.0")
