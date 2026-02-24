from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from core.views import UserViewSet, DepartmentViewSet, index
from admin_office.views import NoticeViewSet
from meeting.api import MeetingRoomViewSet, RoomBookingViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'notices', NoticeViewSet)
router.register(r'meeting-rooms', MeetingRoomViewSet)
router.register(r'room-bookings', RoomBookingViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")), 
    path("accounts/", include("django.contrib.auth.urls")),
    
    # Frontend
     path("", index, name='index'),
     path("core/", include('core.urls', namespace='core')),
     path("hr/", include('hr.urls', namespace='hr')),
     path("docs/", include('docs.urls', namespace='docs')),
     path("meeting/", include('meeting.urls', namespace='meeting')),
     path("finance/", include('finance.urls', namespace='finance')),
     path("admin-office/", include('admin_office.urls', namespace='admin_office')),
     path("trading/", include('trading.urls', namespace='trading')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
