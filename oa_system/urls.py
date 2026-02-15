from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from core.views import UserViewSet, DepartmentViewSet, index
from admin_office.views import NoticeViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'notices', NoticeViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")), 
    path("accounts/", include("django.contrib.auth.urls")),
    
    # Frontend
     path("", index, name='index'),
     path("hr/", include('hr.urls', namespace='hr')),
     path("docs/", include('docs.urls', namespace='docs')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
