from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('employee_id', 'department', 'position', 'phone')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'department', 'position')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'employee_id')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'department')

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'manager', 'created_at')
    search_fields = ('name',)
    list_filter = ('parent',)
