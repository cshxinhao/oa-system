from django.views.generic import ListView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django_fsm import TransitionNotAllowed
from .models import LeaveApplication
from .forms import LeaveApplicationForm
from .permissions import get_pending_leaves_for_approver, can_approve_application

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
                "reviewer",
            )
            .prefetch_related("dates")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        pending_leaves = get_pending_leaves_for_approver(user)
        can_approve = pending_leaves.exists()
        
        # history of approvals
        history_leaves = (
            LeaveApplication.objects.filter(reviewer=user)
            .select_related(
                "applicant",
                "applicant__department",
                "applicant__department__manager",
                "applicant__department__parent",
                "applicant__department__parent__manager",
                "reviewer",
            )
            .prefetch_related("dates")
            .order_by("-updated_at")
        )
            
        context['pending_leaves'] = pending_leaves
        context['history_leaves'] = history_leaves
        context['can_approve'] = can_approve or history_leaves.exists()
        return context

class LeaveCreateView(LoginRequiredMixin, CreateView):
    model = LeaveApplication
    form_class = LeaveApplicationForm
    template_name = 'hr/leave_form.html'
    success_url = reverse_lazy('hr:leave_list')

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
        except TransitionNotAllowed:
            form.add_error(None, "当前申请无法提交，请刷新后重试")
            return self.form_invalid(form)
        messages.success(self.request, "请假申请已提交")
        return redirect(self.success_url)

class LeaveApproveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        leave = get_object_or_404(LeaveApplication, pk=pk)
        
        if not can_approve_application(request.user, leave):
            raise PermissionDenied("您没有权限审批此申请")
            
        if leave.status != LeaveApplication.STATUS_PENDING:
            messages.error(request, "该申请状态已变更，无法审批")
            return redirect('hr:leave_list')
            
        try:
            with transaction.atomic():
                leave.approve()
                leave.reviewer = request.user
                leave.save()
        except TransitionNotAllowed:
            messages.error(request, "该申请状态已变更，无法审批")
            return redirect('hr:leave_list')
        
        messages.success(request, f"已批准 {leave.applicant.get_full_name()} 的请假申请")
        return redirect('hr:leave_list')

class LeaveRejectView(LoginRequiredMixin, View):
    def post(self, request, pk):
        leave = get_object_or_404(LeaveApplication, pk=pk)
        
        if not can_approve_application(request.user, leave):
            raise PermissionDenied("您没有权限审批此申请")
            
        if leave.status != LeaveApplication.STATUS_PENDING:
            messages.error(request, "该申请状态已变更，无法审批")
            return redirect('hr:leave_list')
            
        try:
            with transaction.atomic():
                leave.reject()
                leave.reviewer = request.user
                leave.save()
        except TransitionNotAllowed:
            messages.error(request, "该申请状态已变更，无法拒绝")
            return redirect('hr:leave_list')
        
        messages.warning(request, f"已拒绝 {leave.applicant.get_full_name()} 的请假申请")
        return redirect('hr:leave_list')

class LeaveWithdrawView(LoginRequiredMixin, View):
    def post(self, request, pk):
        leave = get_object_or_404(LeaveApplication, pk=pk)

        if leave.applicant != request.user and not request.user.is_superuser:
            raise PermissionDenied("您没有权限撤回此申请")

        if leave.status != LeaveApplication.STATUS_PENDING:
            messages.error(request, "该申请状态已变更，无法撤回")
            return redirect('hr:leave_list')

        try:
            with transaction.atomic():
                leave.withdraw()
                leave.reviewer = None
                leave.save()
        except TransitionNotAllowed:
            messages.error(request, "该申请状态已变更，无法撤回")
            return redirect('hr:leave_list')

        messages.info(request, "请假申请已撤回")
        return redirect('hr:leave_list')
