from rest_framework import viewsets, permissions
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Notice
from .serializers import NoticeSerializer

class NoticeViewSet(viewsets.ModelViewSet):
    """
    公告 API
    """
    queryset = Notice.objects.filter(is_published=True)
    serializer_class = NoticeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    search_fields = ['title', 'content']

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
    
    def get_queryset(self):
        # 只有管理员可以看到未发布的公告，普通用户只能看已发布的
        if self.request.user.is_staff:
            return Notice.objects.all()
        return Notice.objects.filter(is_published=True)

class NoticeListView(LoginRequiredMixin, ListView):
    model = Notice
    template_name = 'admin_office/notice_list.html'
    context_object_name = 'notices'
    paginate_by = 10

    def get_queryset(self):
        if self.request.user.is_staff:
            return Notice.objects.all().order_by('-published_at')
        return Notice.objects.filter(is_published=True).order_by('-published_at')

class NoticeDetailView(LoginRequiredMixin, DetailView):
    model = Notice
    template_name = 'admin_office/notice_detail.html'
    context_object_name = 'notice'

    def get_queryset(self):
        if self.request.user.is_staff:
            return Notice.objects.all()
        return Notice.objects.filter(is_published=True)
