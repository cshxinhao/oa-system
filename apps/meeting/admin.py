from django.contrib import admin

from .models import MeetingRoom, RoomBooking


@admin.register(MeetingRoom)
class MeetingRoomAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "capacity", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "location")


@admin.register(RoomBooking)
class RoomBookingAdmin(admin.ModelAdmin):
    list_display = ("room", "title", "organizer", "start_at", "end_at", "status", "created_at")
    list_filter = ("status", "room", "start_at")
    search_fields = ("title", "organizer__username", "organizer__first_name", "organizer__last_name")
    autocomplete_fields = ("room", "organizer")

