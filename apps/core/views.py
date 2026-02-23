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

class UserPermissionView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = User
    template_name = 'core/user_permissions.html'
    context_object_name = 'users'

    def test_func(self):
        # Only superusers can access
        return self.request.user.is_superuser

    def get_queryset(self):
        return User.objects.all().order_by('username')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        content_type = ContentType.objects.get(app_label='docs', model='document')
        try:
            permission = Permission.objects.get(content_type=content_type, codename='add_document')
            context['upload_perm'] = permission
            
            # Annotate users for template
            users = list(context['users'])
            for user in users:
                user.has_upload_perm = user.user_permissions.filter(id=permission.id).exists()
            context['users'] = users
            
        except Permission.DoesNotExist:
            context['upload_perm'] = None
            
        return context

    def post(self, request, *args, **kwargs):
        try:
            content_type = ContentType.objects.get(app_label='docs', model='document')
            permission = Permission.objects.get(content_type=content_type, codename='add_document')
        except (ContentType.DoesNotExist, Permission.DoesNotExist):
            messages.error(request, "Permission 'docs.add_document' not found.")
            return redirect('core:user_permissions')
        
        visible_user_ids = set(map(int, request.POST.getlist('visible_user_ids')))
        selected_user_ids = set(map(int, request.POST.getlist('user_ids')))
        
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
        
        messages.success(request, "Permissions updated successfully.")
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

@login_required
def index(request):
    notices = Notice.objects.filter(is_published=True).order_by('-published_at')[:5]
    
    pending_leaves = get_pending_leaves_for_approver(request.user)
    can_approve = pending_leaves.exists()

    return render(
        request,
        'index.html',
        {'notices': notices, 'pending_leaves': pending_leaves, 'can_approve': can_approve},
    )
