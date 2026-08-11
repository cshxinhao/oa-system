from django.urls import path

from .views import BookingCancelView, BookingCreateView, BookingListView, BookedRoomsView, MeetingRoomListView, RoomAvailabilityView


app_name = "meeting"


urlpatterns = [
    path("rooms/", MeetingRoomListView.as_view(), name="room_list"),
    path("bookings/", BookingListView.as_view(), name="booking_list"),
    path("bookings/create/", BookingCreateView.as_view(), name="booking_create"),
    path("bookings/<int:pk>/cancel/", BookingCancelView.as_view(), name="booking_cancel"),
    path("availability/", RoomAvailabilityView.as_view(), name="availability"),
    path("bookings/booked/", BookedRoomsView.as_view(), name="booked_rooms"),
]

