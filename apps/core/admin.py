from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.urls import reverse
from django.utils.html import format_html
from hr.models import LeaveQuota, LeaveApproverSetting
from .models import User, Department

class LeaveQuotaInline(admin.TabularInline):
    model = LeaveQuota
    extra = 0

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('employee_id', 'department', 'position', 'phone', 'can_approve_all_leaves')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'department', 'position', 'can_approve_all_leaves', 'leave_approvers_link')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'employee_id')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'department', 'can_approve_all_leaves')
    inlines = [LeaveQuotaInline]

    @admin.display(description="Leave Approvers")
    def leave_approvers_link(self, obj):
        try:
            setting = obj.leave_approver_setting   # cached by select_related below
        except LeaveApproverSetting.DoesNotExist:
            url = f"{reverse('admin:hr_leaveapproversetting_add')}?user={obj.pk}"
            return format_html('<a href="{}">Configure</a>', url)
        url = reverse('admin:hr_leaveapproversetting_change', args=[setting.pk])
        return format_html('<a href="{}">{} approver(s)</a>', url, len(setting.approvers.all()))

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'leave_approver_setting'
        ).prefetch_related('leave_approver_setting__approvers')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'manager', 'created_at')
    search_fields = ('name',)
    list_filter = ('parent',)
