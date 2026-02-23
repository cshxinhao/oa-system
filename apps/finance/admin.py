from django.contrib import admin
from .models import ReimbursementRequest, ExpenseItem

class ExpenseItemInline(admin.TabularInline):
    model = ExpenseItem
    extra = 0

@admin.register(ReimbursementRequest)
class ReimbursementRequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'requester', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'description', 'requester__username', 'requester__first_name')
    inlines = [ExpenseItemInline]
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ExpenseItem)
class ExpenseItemAdmin(admin.ModelAdmin):
    list_display = ('request', 'expense_type', 'amount', 'currency', 'converted_amount', 'expense_date')
    list_filter = ('expense_type', 'currency', 'expense_date')
    search_fields = ('description', 'request__title')
