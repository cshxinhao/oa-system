from django.urls import path
from .views import UserPermissionView, ProfileView, SettingsView

app_name = 'core'

urlpatterns = [
    path('permissions/', UserPermissionView.as_view(), name='user_permissions'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('settings/', SettingsView.as_view(), name='settings'),
]
