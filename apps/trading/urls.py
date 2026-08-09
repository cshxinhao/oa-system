from django.urls import path
from .views import TradingRequestView

app_name = 'trading'

urlpatterns = [
    path('request/', TradingRequestView.as_view(), name='request'),
]
