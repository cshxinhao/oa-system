import calendar
from collections import defaultdict
from datetime import date, timedelta

from django.views.generic import ListView, CreateView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django_fsm import TransitionNotAllowed

from core.models import Department
from .models import LeaveApplication
from .forms import LeaveApplicationForm
from .permissions import get_pending_leaves_for_approver, can_approve_application
from .services import quota_summary, quota_summaries
from .mail import notify_approver_of_pending_leave, notify_applicant_of_outcome

class LeaveListView(LoginRequiredMixin, ListView):
    model = LeaveApplication
    template_name = 'hr/leave_list.html'
    context_object_name = 'leaves'

    def get_queryset(self):
        user = self.request.user
        return (
            LeaveApplication.objects.filter(applicant=user)
            .select_related(
                "applicant",
                "applicant__department",
                "applicant__department__manager",
                "applicant__department__parent",
                "applicant__department__parent__manager",
                "approver",
                "reviewer",
            )
            .prefetch_related("dates")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        pending_leaves = get_pending_leaves_for_approver(user)
        for leave in pending_leaves:
            leave.applicant_quota_summary = quota_summary(leave.applicant)
        can_approve = pending_leaves.exists()

        # history of approvals: leaves this user actually reviewed
        history_leaves = (
            LeaveApplication.objects.filter(reviewer=user)
            .select_related(
                "applicant",
                "applicant__department",
                "applicant__department__manager",
                "applicant__department__parent",
                "applicant__department__parent__manager",
                "approver",
            )
            .prefetch_related("dates")
            .order_by("-updated_at")
        )

        context['pending_leaves'] = pending_leaves
        context['history_leaves'] = history_leaves
        context['can_approve'] = can_approve or history_leaves.exists()
        context['annual_quota'] = quota_summary(user)
        context['quota_list'] = quota_summaries(user)
        return context

class LeaveCreateView(LoginRequiredMixin, CreateView):
    model = LeaveApplication
    form_class = LeaveApplicationForm
    template_name = 'hr/leave_form.html'
    success_url = reverse_lazy('hr:leave_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.applicant = self.request.user
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.applicant = self.request.user
                self.object.save()
                
                # Handle discontinuous dates
                parsed_dates = form.cleaned_data.get('parsed_dates')
                if parsed_dates:
                    from .models import LeaveApplicationDate
                    for d in parsed_dates:
                        LeaveApplicationDate.objects.create(application=self.object, date=d)
                
                self.object.submit()
                self.object.save()
                leave = self.object  # local capture, avoids late-binding surprises
                transaction.on_commit(lambda: notify_approver_of_pending_leave(leave))
        except TransitionNotAllowed:
            form.add_error(None, "The application cannot be submitted at this time. Please refresh and try again.")
            return self.form_invalid(form)
        messages.success(self.request, "Leave application submitted")
        return redirect(self.success_url)

class LeaveApproveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        leave = get_object_or_404(LeaveApplication, pk=pk)
        
        if not can_approve_application(request.user, leave):
            raise PermissionDenied("You do not have permission to approve this application.")

        if leave.status != LeaveApplication.STATUS_PENDING:
            messages.error(request, "The application status has changed and it can no longer be approved.")
            return redirect('hr:leave_list')

        try:
            with transaction.atomic():
                leave.approve()
                leave.reviewer = request.user
                leave.save()
                transaction.on_commit(lambda: notify_applicant_of_outcome(leave))
        except TransitionNotAllowed:
            messages.error(request, "The application status has changed and it can no longer be approved.")
            return redirect('hr:leave_list')

        messages.success(request, f"Approved the leave application of {leave.applicant.get_full_name()}")
        return redirect('hr:leave_list')

class LeaveRejectView(LoginRequiredMixin, View):
    def post(self, request, pk):
        leave = get_object_or_404(LeaveApplication, pk=pk)
        
        if not can_approve_application(request.user, leave):
            raise PermissionDenied("You do not have permission to approve this application.")

        if leave.status != LeaveApplication.STATUS_PENDING:
            messages.error(request, "The application status has changed and it can no longer be rejected.")
            return redirect('hr:leave_list')

        try:
            with transaction.atomic():
                leave.reject()
                leave.reviewer = request.user
                leave.save()
                transaction.on_commit(lambda: notify_applicant_of_outcome(leave))
        except TransitionNotAllowed:
            messages.error(request, "The application status has changed and it can no longer be rejected.")
            return redirect('hr:leave_list')

        messages.warning(request, f"Rejected the leave application of {leave.applicant.get_full_name()}")
        return redirect('hr:leave_list')

class LeaveWithdrawView(LoginRequiredMixin, View):
    def post(self, request, pk):
        leave = get_object_or_404(LeaveApplication, pk=pk)

        if leave.applicant != request.user and not request.user.is_superuser:
            raise PermissionDenied("You do not have permission to withdraw this application.")

        if leave.status != LeaveApplication.STATUS_PENDING:
            messages.error(request, "The application status has changed and it can no longer be withdrawn.")
            return redirect('hr:leave_list')

        try:
            with transaction.atomic():
                leave.withdraw()
                leave.save()
        except TransitionNotAllowed:
            messages.error(request, "The application status has changed and it can no longer be withdrawn.")
            return redirect('hr:leave_list')

        messages.info(request, "Leave application withdrawn")
        return redirect('hr:leave_list')

LEAVE_TYPE_BADGE_CLASSES = {
    LeaveApplication.TYPE_SICK: 'bg-danger',
    LeaveApplication.TYPE_ANNUAL: 'bg-primary',
    LeaveApplication.TYPE_BIRTHDAY: 'bg-warning',
    LeaveApplication.TYPE_MATERNITY: 'bg-info',
    LeaveApplication.TYPE_PATERNITY: 'bg-success',
    LeaveApplication.TYPE_COMPASSIONATE: 'bg-secondary',
    LeaveApplication.TYPE_NO_PAY: 'bg-dark',
    LeaveApplication.TYPE_BUSINESS_TRIP: 'bg-business-trip',
}


class LeaveScheduleView(LoginRequiredMixin, TemplateView):
    """Monthly calendar of approved leave for all employees."""
    template_name = 'hr/leave_schedule.html'

    def _parse_year_month(self):
        """Return (year, month) from GET params, defaulting to the current month."""
        today = date.today()
        try:
            year = int(self.request.GET.get('year', today.year))
            month = int(self.request.GET.get('month', today.month))
            if not (2000 <= year <= 2100) or not (1 <= month <= 12):
                raise ValueError
        except (TypeError, ValueError):
            return today.year, today.month
        return year, month

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        year, month = self._parse_year_month()
        today = date.today()

        month_start = date(year, month, 1)
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        prev_first = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
        next_first = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

        # Department filter (invalid id -> no filter)
        department = None
        dep_id = self.request.GET.get('department')
        if dep_id:
            department = Department.objects.filter(pk=dep_id).first()

        # Approved leaves overlapping the month.
        # Branch A: discontinuous leaves with dates rows inside the month.
        # Branch B: contiguous ranges WITHOUT dates rows overlapping the month
        #           (also covers half-day leaves: single-day, start_date == end_date).
        leaves = (
            LeaveApplication.objects
            .filter(status=LeaveApplication.STATUS_APPROVED)
            .filter(
                Q(dates__date__range=(month_start, month_end))
                | Q(dates__isnull=True,
                    start_date__lte=month_end,
                    end_date__gte=month_start)
            )
            .select_related('applicant', 'applicant__department')
            .prefetch_related('dates')
            .distinct()
        )
        if department:
            leaves = leaves.filter(applicant__department=department)

        # Expand each application into per-day entries (mirrors services.leave_used_days)
        entries_by_day = defaultdict(list)
        for app in leaves:
            name = app.applicant.get_full_name() or app.applicant.username
            entry = {
                'name': name,
                'leave_type_display': app.get_leave_type_display(),
                'badge_class': LEAVE_TYPE_BADGE_CLASSES[app.leave_type],
                'is_half_day': app.is_half_day,
                'half_day_period': app.half_day_period,  # 'am' / 'pm'
            }
            days = set()  # set -> no duplicate day entries
            if app.is_half_day:
                if month_start <= app.start_date <= month_end:
                    days.add(app.start_date)
            else:
                rows = [d.date for d in app.dates.all()
                        if month_start <= d.date <= month_end]
                if rows:
                    days.update(rows)
                else:
                    low = max(app.start_date, month_start)
                    high = min(app.end_date, month_end)
                    if low <= high:  # bounded by the month length (~31 iterations max)
                        d = low
                        while d <= high:
                            days.add(d)
                            d += timedelta(days=1)
            for day in days:
                entries_by_day[day].append(entry)

        for day_entries in entries_by_day.values():
            day_entries.sort(key=lambda e: e['name'].lower())

        # Monday-first month matrix
        weeks = []
        for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
            weeks.append([{
                'date': day,
                'in_month': day.month == month,
                'is_today': day == today,
                'is_weekend': day.weekday() >= 5,
                'entries': entries_by_day.get(day, []),
            } for day in week])

        context.update({
            'year': year,
            'month': month,
            'month_label': month_start.strftime('%B %Y'),
            'prev_year': prev_first.year,
            'prev_month': prev_first.month,
            'prev_month_name': prev_first.strftime('%B'),
            'next_year': next_first.year,
            'next_month': next_first.month,
            'next_month_name': next_first.strftime('%B'),
            'department_param': f'&department={department.pk}' if department else '',
            'departments': Department.objects.order_by('name'),
            'selected_department': department.pk if department else None,
            'weeks': weeks,
            'total_entries': sum(len(v) for v in entries_by_day.values()),
            'leave_type_legend': [
                {'label': label, 'badge_class': LEAVE_TYPE_BADGE_CLASSES[code]}
                for code, label in LeaveApplication.TYPE_CHOICES
            ],
        })
        return context
