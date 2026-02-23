from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import ReimbursementRequest, ExpenseItem
from .forms import ReimbursementRequestForm, ExpenseItemFormSet, CheckerSelectionForm

class ReimbursementListView(LoginRequiredMixin, ListView):
    model = ReimbursementRequest
    template_name = 'finance/reimbursement_list.html'
    context_object_name = 'requests'

    def get_queryset(self):
        user = self.request.user
        queryset = ReimbursementRequest.objects.all()
        
        # Superusers see everything
        if user.is_superuser:
            return queryset.order_by('-created_at')
            
        # Checkers see requests assigned to them
        if user.has_perm('finance.can_check_reimbursement'):
             return queryset.filter(
                Q(requester=user) | 
                Q(checker=user) |
                Q(status__in=['CHECKED', 'APPROVED', 'REJECTED', 'PAID'])
            ).distinct().order_by('-created_at')
            
        # Managers/Approvers logic (simplified for list view, detailed permissions handled in detail view)
        # For now, if staff, show all non-drafts to allow finding requests to approve
        if user.is_staff:
            return queryset.filter(
                Q(requester=user) | 
                Q(status__in=['SUBMITTED', 'CHECKED', 'APPROVED', 'REJECTED', 'PAID'])
            ).distinct().order_by('-created_at')

        # Regular users only see their own
        return queryset.filter(requester=user).order_by('-created_at')

class ReimbursementDetailView(LoginRequiredMixin, DetailView):
    model = ReimbursementRequest
    template_name = 'finance/reimbursement_detail.html'
    context_object_name = 'reimbursement'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        reimbursement = self.object
        
        # Determine if user can check
        context['can_check'] = (
            reimbursement.status == 'SUBMITTED' and 
            reimbursement.checker == user and
            user.has_perm('finance.can_check_reimbursement')
        ) or user.is_superuser
        
        # Determine if user can approve
        # Logic: Status is CHECKED AND (User is calculated approver OR Superuser)
        approver = self.get_approver(reimbursement)
        context['can_approve'] = (
            reimbursement.status == 'CHECKED' and
            (user == approver or user.is_superuser)
        )
        context['calculated_approver'] = approver
        
        return context
        
    def get_approver(self, reimbursement):
        requester = reimbursement.requester
        if not requester.department:
            return None # No department, handled by superuser/admin
            
        # If requester is not manager, approver is their manager
        if requester.department.manager != requester:
            return requester.department.manager
        
        # If requester IS manager, approver is parent department manager
        if requester.department.parent:
            return requester.department.parent.manager
            
        return None

    def get_queryset(self):
        # Allow wide access for detail view, permissions handled in template/actions
        return ReimbursementRequest.objects.all()

class ReimbursementCreateView(LoginRequiredMixin, CreateView):
    model = ReimbursementRequest
    form_class = ReimbursementRequestForm
    template_name = 'finance/reimbursement_form.html'
    success_url = reverse_lazy('finance:reimbursement_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items'] = ExpenseItemFormSet(self.request.POST, self.request.FILES)
        else:
            context['items'] = ExpenseItemFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            form.instance.requester = self.request.user
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
            else:
                return self.form_invalid(form)
        messages.success(self.request, 'Reimbursement request created successfully.')
        return super().form_valid(form)

class ReimbursementUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ReimbursementRequest
    form_class = ReimbursementRequestForm
    template_name = 'finance/reimbursement_form.html'
    success_url = reverse_lazy('finance:reimbursement_list')

    def test_func(self):
        obj = self.get_object()
        return obj.requester == self.request.user and obj.status == 'DRAFT'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items'] = ExpenseItemFormSet(self.request.POST, self.request.FILES, instance=self.object)
        else:
            context['items'] = ExpenseItemFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
            else:
                return self.form_invalid(form)
        messages.success(self.request, 'Reimbursement request updated successfully.')
        return super().form_valid(form)

class ReimbursementDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ReimbursementRequest
    template_name = 'finance/reimbursement_confirm_delete.html'
    success_url = reverse_lazy('finance:reimbursement_list')

    def test_func(self):
        obj = self.get_object()
        return obj.requester == self.request.user and obj.status == 'DRAFT'
    
    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Reimbursement request deleted successfully.')
        return super().delete(request, *args, **kwargs)

def submit_reimbursement(request, pk):
    reimbursement = get_object_or_404(ReimbursementRequest, pk=pk, requester=request.user)
    
    if reimbursement.status != 'DRAFT':
        messages.error(request, 'Only draft requests can be submitted.')
        return redirect('finance:reimbursement_list')

    if request.method == 'POST':
        form = CheckerSelectionForm(request.POST)
        if form.is_valid():
            reimbursement.status = 'SUBMITTED'
            reimbursement.checker = form.cleaned_data['checker']
            reimbursement.save()
            messages.success(request, 'Reimbursement request submitted to checker successfully.')
            return redirect('finance:reimbursement_list')
    else:
        form = CheckerSelectionForm()
        
    return render(request, 'finance/reimbursement_submit.html', {
        'reimbursement': reimbursement,
        'form': form
    })

def check_reimbursement(request, pk):
    reimbursement = get_object_or_404(ReimbursementRequest, pk=pk)
    
    # Permission check: Must be the assigned checker or superuser
    if not (request.user == reimbursement.checker or request.user.is_superuser):
        messages.error(request, 'You are not authorized to check this request.')
        return redirect('finance:reimbursement_detail', pk=pk)
        
    if reimbursement.status != 'SUBMITTED':
        messages.error(request, 'Request is not in submitted state.')
        return redirect('finance:reimbursement_detail', pk=pk)
        
    if request.method == 'POST':
        reimbursement.status = 'CHECKED'
        reimbursement.checked_at = timezone.now()
        reimbursement.save()
        messages.success(request, 'Request checked successfully. Forwarded for approval.')
        
    return redirect('finance:reimbursement_detail', pk=pk)

def approve_reject_reimbursement(request, pk):
    reimbursement = get_object_or_404(ReimbursementRequest, pk=pk)
    
    # Resolve Approver
    view = ReimbursementDetailView()
    view.request = request
    expected_approver = view.get_approver(reimbursement)
    
    # Permission Check
    if not (request.user == expected_approver or request.user.is_superuser):
        messages.error(request, 'You are not authorized to approve requests.')
        return redirect('finance:reimbursement_list')
        
    if reimbursement.status != 'CHECKED':
        messages.error(request, 'Request must be checked before approval.')
        return redirect('finance:reimbursement_detail', pk=pk)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('rejection_reason', '')
        
        if action == 'approve':
            reimbursement.status = 'APPROVED'
            reimbursement.approver = request.user
            reimbursement.save()
            messages.success(request, f'Request {reimbursement.title} approved.')
        elif action == 'reject':
            reimbursement.status = 'REJECTED'
            reimbursement.approver = request.user
            reimbursement.rejection_reason = reason
            reimbursement.save()
            messages.success(request, f'Request {reimbursement.title} rejected.')
            
    return redirect('finance:reimbursement_detail', pk=pk)
