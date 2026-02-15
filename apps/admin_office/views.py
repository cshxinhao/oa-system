from rest_framework import viewsets, permissions
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
