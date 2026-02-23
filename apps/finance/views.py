from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from .models import ReimbursementRequest, ExpenseItem
from .forms import ReimbursementRequestForm, ExpenseItemFormSet

class ReimbursementListView(LoginRequiredMixin, ListView):
    model = ReimbursementRequest
    template_name = 'finance/reimbursement_list.html'
    context_object_name = 'requests'

    def get_queryset(self):
        user = self.request.user
        queryset = ReimbursementRequest.objects.all()
        
        if user.is_staff or user.is_superuser:
            # Staff can see all submitted requests + their own drafts
            return queryset.filter(
                Q(requester=user) | 
                Q(status__in=['SUBMITTED', 'APPROVED', 'REJECTED', 'PAID'])
            ).distinct().order_by('-created_at')
        else:
            # Regular users only see their own
            return queryset.filter(requester=user).order_by('-created_at')

class ReimbursementDetailView(LoginRequiredMixin, DetailView):
    model = ReimbursementRequest
    template_name = 'finance/reimbursement_detail.html'
    context_object_name = 'reimbursement'

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return ReimbursementRequest.objects.all()
        return ReimbursementRequest.objects.filter(requester=user)

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
    if reimbursement.status == 'DRAFT':
        reimbursement.status = 'SUBMITTED'
        reimbursement.save()
        messages.success(request, 'Reimbursement request submitted successfully.')
    else:
        messages.error(request, 'Only draft requests can be submitted.')
    return redirect('finance:reimbursement_list')

def approve_reject_reimbursement(request, pk):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'You are not authorized to approve requests.')
        return redirect('finance:reimbursement_list')
        
    reimbursement = get_object_or_404(ReimbursementRequest, pk=pk)
    
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
