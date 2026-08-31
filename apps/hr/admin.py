from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import LeaveApplication, LeaveQuota, LeaveApproverSetting
from .permissions import get_org_approver

User = get_user_model()

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

@admin.register(LeaveApproverSetting)
class LeaveApproverSettingAdmin(admin.ModelAdmin):
    list_display = ('user', 'approver_count', 'default_org_approver', 'updated_at')
    search_fields = ('user__username', 'user__first_name', 'approvers__username')
    filter_horizontal = ('approvers',)
    fields = ('user', 'approvers')

    @admin.display(description="Approver Count")
    def approver_count(self, obj):
        return len(obj.approvers.all())  # uses prefetch cache

    @admin.display(description="Default Org Approver")
    def default_org_approver(self, obj):
        org = get_org_approver(obj.user)
        return org if org else "-"

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related(
                'user__department__manager',
                'user__department__parent__manager',
            )
            .prefetch_related('approvers')
        )

    def get_readonly_fields(self, request, obj=None):
        # Lock `user` once the row exists so a config can't be reassigned;
        # keep it editable on the add form so the ?user= pre-fill is visible.
        if obj:
            return ('user',)
        return ()

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        user_id = request.GET.get('user')
        if user_id:
            initial['user'] = user_id
            try:
                org = get_org_approver(User.objects.get(pk=user_id))
            except User.DoesNotExist:
                org = None
            if org:
                # strings mirror the built-in M2M GET handling
                initial['approvers'] = [str(org.pk)]
        return initial
