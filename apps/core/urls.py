from django.urls import path
from .views import UserPermissionView

app_name = 'core'

urlpatterns = [
    path('permissions/', UserPermissionView.as_view(), name='user_permissions'),
]
