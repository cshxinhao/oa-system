from django.urls import path
from .views import LeaveListView, LeaveCreateView, LeaveApproveView, LeaveRejectView, LeaveWithdrawView

app_name = 'hr'

urlpatterns = [
    path('leaves/', LeaveListView.as_view(), name='leave_list'),
    path('leaves/create/', LeaveCreateView.as_view(), name='leave_create'),
    path('leaves/<int:pk>/approve/', LeaveApproveView.as_view(), name='leave_approve'),
    path('leaves/<int:pk>/reject/', LeaveRejectView.as_view(), name='leave_reject'),
    path('leaves/<int:pk>/withdraw/', LeaveWithdrawView.as_view(), name='leave_withdraw'),
]
