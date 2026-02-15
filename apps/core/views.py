from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import User, Department
from .serializers import UserSerializer, DepartmentSerializer
from admin_office.models import Notice
from hr.models import LeaveApplication
from hr.permissions import approvable_department_ids

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
    pending_leaves = LeaveApplication.objects.none()
    can_approve = False

    department_ids = approvable_department_ids(request.user)
    if department_ids is None:
        can_approve = True
        pending_leaves = LeaveApplication.objects.filter(status=LeaveApplication.STATUS_PENDING)
    elif department_ids:
        can_approve = True
        pending_leaves = LeaveApplication.objects.filter(
            status=LeaveApplication.STATUS_PENDING,
            applicant__department_id__in=department_ids,
        ).exclude(applicant=request.user)

    return render(
        request,
        'index.html',
        {'notices': notices, 'pending_leaves': pending_leaves, 'can_approve': can_approve},
    )
