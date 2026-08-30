from django.contrib import admin
from .models import LeaveApplication, LeaveQuota

@admin.register(LeaveApplication)
class LeaveApplicationAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'leave_type', 'start_date', 'end_date', 'status', 'approver', 'reviewer', 'created_at')
    list_filter = ('status', 'leave_type', 'created_at')
    search_fields = ('applicant__username', 'reason')
    readonly_fields = ('status',) # 状态由工作流控制

@admin.register(LeaveQuota)
class LeaveQuotaAdmin(admin.ModelAdmin):
    list_display = ('user', 'year', 'leave_type', 'total_days', 'used_days', 'remaining_days')
    search_fields = ('user__username', 'user__first_name')
    list_filter = ('year', 'leave_type')
