from rest_framework import serializers
from .models import User, Department

class DepartmentSerializer(serializers.ModelSerializer):
    manager_name = serializers.ReadOnlyField(source='manager.get_full_name')

    class Meta:
        model = Department
        fields = ['id', 'name', 'parent', 'manager', 'manager_name', 'created_at']

class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.ReadOnlyField(source='department.name')
    full_name = serializers.ReadOnlyField(source='get_full_name')

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'full_name', 'employee_id', 'department', 'department_name', 'position', 'phone']
