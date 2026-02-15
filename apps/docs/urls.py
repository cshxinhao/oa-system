from django.urls import path
from .views import DocumentListView, DocumentCreateView

app_name = 'docs'

urlpatterns = [
    path('documents/', DocumentListView.as_view(), name='doc_list'),
    path('documents/create/', DocumentCreateView.as_view(), name='doc_create'),
]
