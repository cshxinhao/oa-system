from django.urls import path
from . import views

app_name = 'finance'

urlpatterns = [
    path('reimbursements/', views.ReimbursementListView.as_view(), name='reimbursement_list'),
    path('reimbursements/create/', views.ReimbursementCreateView.as_view(), name='reimbursement_create'),
    path('reimbursements/<int:pk>/', views.ReimbursementDetailView.as_view(), name='reimbursement_detail'),
    path('reimbursements/<int:pk>/update/', views.ReimbursementUpdateView.as_view(), name='reimbursement_update'),
    path('reimbursements/<int:pk>/delete/', views.ReimbursementDeleteView.as_view(), name='reimbursement_delete'),
    path('reimbursements/<int:pk>/submit/', views.submit_reimbursement, name='reimbursement_submit'),
    path('reimbursements/<int:pk>/approve/', views.approve_reject_reimbursement, name='reimbursement_approve'),
]
