from django.contrib import admin
from .models import LeaveApplication

@admin.register(LeaveApplication)
class LeaveApplicationAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'leave_type', 'start_date', 'end_date', 'status', 'approver', 'reviewer', 'created_at')
    list_filter = ('status', 'leave_type', 'created_at')
    search_fields = ('applicant__username', 'reason')
    readonly_fields = ('status',) # 状态由工作流控制

    def approver(self, obj):
        return obj.expected_approver

    approver.short_description = "Approver"
