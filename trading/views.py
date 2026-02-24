from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

class TradingRequestView(LoginRequiredMixin, TemplateView):
    template_name = "trading/request.html"
