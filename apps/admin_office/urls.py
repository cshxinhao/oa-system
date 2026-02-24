from django.urls import path
from . import views

app_name = 'admin_office'

urlpatterns = [
    path('notices/', views.NoticeListView.as_view(), name='notice_list'),
    path('notices/<int:pk>/', views.NoticeDetailView.as_view(), name='notice_detail'),
]
