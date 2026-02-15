from datetime import date

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from core.models import Department, User
from hr.models import LeaveApplication


class LeaveFlowTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="研发部")
        self.employee = User.objects.create_user(
            username="employee",
            password="pwd",
            department=self.department,
        )

    def test_submit_leave_redirect_and_list_renders_with_null_reviewer(self):
        self.client.force_login(self.employee)
        resp = self.client.post(
            reverse("hr:leave_create"),
            data={
                "leave_type": "sick",
                "start_date": "2026-02-14",
                "end_date": "2026-02-15",
                "reason": "身体不适",
            },
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "请假申请已提交")
        self.assertEqual(LeaveApplication.objects.filter(applicant=self.employee).count(), 1)

    def test_date_range_validation(self):
        self.client.force_login(self.employee)
        resp = self.client.post(
            reverse("hr:leave_create"),
            data={
                "leave_type": "sick",
                "start_date": "2026-02-16",
                "end_date": "2026-02-15",
                "reason": "日期填错",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "结束日期不能早于开始日期")
        self.assertEqual(LeaveApplication.objects.filter(applicant=self.employee).count(), 0)

    def test_senior_manager_can_see_tab_and_approve_own_department(self):
        leader = User.objects.create_user(
            username="leader",
            password="pwd",
            department=self.department,
        )
        group, _ = Group.objects.get_or_create(name="Senior Manager")
        leader.groups.add(group)

        leave = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="sick",
            start_date=date(2026, 2, 14),
            end_date=date(2026, 2, 15),
            reason="测试审批",
        )
        leave.submit()
        leave.save()

        self.client.force_login(leader)
        resp = self.client.get(reverse("hr:leave_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "请假审批")

        resp2 = self.client.post(reverse("hr:leave_approve", args=[leave.pk]), follow=True)
        self.assertEqual(resp2.status_code, 200)
        status = LeaveApplication.objects.values_list("status", flat=True).get(pk=leave.pk)
        reviewer = LeaveApplication.objects.values_list("reviewer__username", flat=True).get(pk=leave.pk)
        self.assertEqual(status, LeaveApplication.STATUS_APPROVED)
        self.assertEqual(reviewer, leader.username)

    def test_dashboard_shows_leave_approval_for_approver(self):
        leader = User.objects.create_user(
            username="leader2",
            password="pwd",
            department=self.department,
        )
        group, _ = Group.objects.get_or_create(name="Senior Manager")
        leader.groups.add(group)

        leave = LeaveApplication.objects.create(
            applicant=self.employee,
            leave_type="sick",
            start_date=date(2026, 2, 14),
            end_date=date(2026, 2, 15),
            reason="仪表盘审批",
        )
        leave.submit()
        leave.save()

        self.client.force_login(leader)
        resp = self.client.get(reverse("index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "请假审批")
        self.assertContains(resp, "仪表盘审批")
        self.assertContains(resp, reverse("hr:leave_approve", args=[leave.pk]))
