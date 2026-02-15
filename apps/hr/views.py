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
from .permissions import approvable_department_ids

class LeaveListView(LoginRequiredMixin, ListView):
    model = LeaveApplication
    template_name = 'hr/leave_list.html'
    context_object_name = 'leaves'

    def get_queryset(self):
        user = self.request.user
        queryset = LeaveApplication.objects.filter(applicant=user)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        pending_leaves = LeaveApplication.objects.none()
        can_approve = False
        
        department_ids = approvable_department_ids(user)
        if department_ids is None:
            can_approve = True
            pending_leaves = LeaveApplication.objects.filter(status=LeaveApplication.STATUS_PENDING)
        elif department_ids:
            can_approve = True
            pending_leaves = LeaveApplication.objects.filter(
                status=LeaveApplication.STATUS_PENDING,
                applicant__department_id__in=department_ids,
            ).exclude(applicant=user)
            
        context['pending_leaves'] = pending_leaves
        context['can_approve'] = can_approve
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
        
        department_ids = approvable_department_ids(request.user)
        allowed = (
            department_ids is None
            or (leave.applicant.department_id and leave.applicant.department_id in department_ids)
        )
        if not allowed:
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
        
        department_ids = approvable_department_ids(request.user)
        allowed = (
            department_ids is None
            or (leave.applicant.department_id and leave.applicant.department_id in department_ids)
        )
        if not allowed:
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
