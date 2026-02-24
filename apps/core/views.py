from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib import messages
from django.views.generic import ListView
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import User, Department
from .serializers import UserSerializer, DepartmentSerializer
from admin_office.models import Notice
from hr.models import LeaveApplication
from hr.permissions import get_pending_leaves_for_approver
from finance.models import ReimbursementRequest

class UserPermissionView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'core/user_permissions.html'
    context_object_name = 'users'

    MANAGED_PERMISSIONS = [
        {'app': 'docs', 'model': 'document', 'codename': 'add_document', 'label': 'Upload Documents'},
        {'app': 'finance', 'model': 'reimbursementrequest', 'codename': 'can_check_reimbursement', 'label': 'Check Reimbursements'},
    ]

    def test_func(self):
        # Only superusers can access
        return self.request.user.is_superuser

    def get_queryset(self):
        return User.objects.all().order_by('username')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Load permission objects
        permissions_data = []
        for perm_def in self.MANAGED_PERMISSIONS:
            try:
                content_type = ContentType.objects.get(app_label=perm_def['app'], model=perm_def['model'])
                permission = Permission.objects.get(content_type=content_type, codename=perm_def['codename'])
                permissions_data.append({
                    'def': perm_def,
                    'obj': permission
                })
            except (ContentType.DoesNotExist, Permission.DoesNotExist):
                continue
                
        context['managed_permissions'] = permissions_data
        
        # Annotate users
        users = list(context['users'])
        for user in users:
            user_perms = set(user.user_permissions.values_list('id', flat=True))
            user.permission_states = []
            for p in permissions_data:
                perm_id = p['obj'].id
                user.permission_states.append({
                    'codename': p['def']['codename'],
                    'has_perm': (perm_id in user_perms)
                })
                
        context['users'] = users
        return context

    def post(self, request, *args, **kwargs):
        codename = request.POST.get('permission_codename')
        
        # Find the permission definition
        perm_def = next((p for p in self.MANAGED_PERMISSIONS if p['codename'] == codename), None)
        
        if not perm_def:
            messages.error(request, "Invalid permission specified.")
            return redirect('core:user_permissions')
            
        try:
            content_type = ContentType.objects.get(app_label=perm_def['app'], model=perm_def['model'])
            permission = Permission.objects.get(content_type=content_type, codename=perm_def['codename'])
        except (ContentType.DoesNotExist, Permission.DoesNotExist):
            messages.error(request, f"Permission '{codename}' not found in database.")
            return redirect('core:user_permissions')
        
        # Process users for this specific permission
        # visible_user_ids ensures we only modify users that were displayed on the page
        visible_user_ids = set(map(int, request.POST.getlist('visible_user_ids')))
        
        # selected_user_ids are the ones checked for THIS permission
        selected_user_ids = set(map(int, request.POST.getlist(f'user_ids_{codename}')))
        
        # Get users who currently have permission AND are in the visible list
        current_holders = User.objects.filter(user_permissions=permission, id__in=visible_user_ids)
        current_ids = set(current_holders.values_list('id', flat=True))
        
        # Users to remove: Currently have it (and visible), but not selected
        to_remove = current_ids - selected_user_ids
        
        # Users to add: Selected, but don't currently have it
        to_add = selected_user_ids - current_ids
        
        if to_remove:
            for user in User.objects.filter(id__in=to_remove):
                user.user_permissions.remove(permission)
                
        if to_add:
            for user in User.objects.filter(id__in=to_add):
                user.user_permissions.add(permission)
        
        messages.success(request, f"Permissions for '{perm_def['label']}' updated successfully.")
        return redirect('core:user_permissions')

class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    员工列表 API
    """
    queryset = User.objects.all().order_by('employee_id')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['department', 'position']
    search_fields = ['username', 'first_name', 'last_name', 'employee_id']

class DepartmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    部门 API
    """
    queryset = Department.objects.all().order_by('name')
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name']

def get_approver_for_reimbursement(reimbursement):
    """Helper to determine the approver for a reimbursement request."""
    requester = reimbursement.requester
    if not requester.department:
        return None 
    
    # If requester is not manager, approver is their manager
    if requester.department.manager != requester:
        return requester.department.manager
    
    # If requester IS manager, approver is parent department manager
    if requester.department.parent:
        return requester.department.parent.manager
        
    return None

@login_required
def index(request):
    notices = Notice.objects.filter(is_published=True).order_by('-published_at')[:5]
    
    # Pending Leaves
    pending_leaves = get_pending_leaves_for_approver(request.user)
    
    # Pending Reimbursements
    pending_reimbursements = []
    
    # 1. Check if user is a checker and has submitted requests assigned
    if request.user.has_perm('finance.can_check_reimbursement'):
        checks = ReimbursementRequest.objects.filter(
            status='SUBMITTED', 
            checker=request.user
        )
        for req in checks:
            req.todo_type = 'reimbursement_check'
            pending_reimbursements.append(req)
            
    # 2. Check if user is an approver for any checked requests
    # Get all CHECKED requests
    checked_requests = ReimbursementRequest.objects.filter(status='CHECKED')
    
    for req in checked_requests:
        approver = get_approver_for_reimbursement(req)
        if approver == request.user or request.user.is_superuser:
            req.todo_type = 'reimbursement_approve'
            pending_reimbursements.append(req)
    
    # Mark leave items for the template
    for leave in pending_leaves:
        leave.todo_type = 'leave_approve'
    
    # Combine and Sort
    # We need to convert querysets to lists to combine them
    todo_list = list(pending_leaves) + list(pending_reimbursements)
    
    # Sort by creation date (newest first) - assuming both have created_at/start_date
    # Reimbursement has created_at, Leave has start_date (or created_at if exists)
    # Let's just append for now, or sort if possible.
    
    has_todo = len(todo_list) > 0

    return render(
        request,
        'index.html',
        {
            'notices': notices, 
            'todo_list': todo_list,
            'has_todo': has_todo,
            'can_approve': has_todo # Keeping for backward compatibility if needed, but logic changed
        },
    )
