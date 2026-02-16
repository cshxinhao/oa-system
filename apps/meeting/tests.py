from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import MeetingRoom, RoomBooking
from .services import room_free_slots


class RoomBookingModelTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username="u1", password="pass12345")
        self.room = MeetingRoom.objects.create(name="A101", location="1F", capacity=8, is_active=True)
        self.tz = timezone.get_current_timezone()

    def _dt(self, day: date, t: time) -> datetime:
        return timezone.make_aware(datetime.combine(day, t), timezone=self.tz)

    def test_booking_overlap_rejected(self):
        day = date(2026, 2, 15)
        RoomBooking.objects.create(
            room=self.room,
            organizer=self.user,
            title="b1",
            start_at=self._dt(day, time(10, 0)),
            end_at=self._dt(day, time(11, 0)),
        )

        b2 = RoomBooking(
            room=self.room,
            organizer=self.user,
            title="b2",
            start_at=self._dt(day, time(10, 30)),
            end_at=self._dt(day, time(11, 30)),
        )
        with self.assertRaises(ValidationError):
            b2.full_clean()

    def test_booking_touching_edge_allowed(self):
        day = date(2026, 2, 15)
        RoomBooking.objects.create(
            room=self.room,
            organizer=self.user,
            title="b1",
            start_at=self._dt(day, time(10, 0)),
            end_at=self._dt(day, time(11, 0)),
        )

        b2 = RoomBooking(
            room=self.room,
            organizer=self.user,
            title="b2",
            start_at=self._dt(day, time(11, 0)),
            end_at=self._dt(day, time(12, 0)),
        )
        b2.full_clean()

    def test_canceled_booking_not_conflicting(self):
        day = date(2026, 2, 15)
        b1 = RoomBooking.objects.create(
            room=self.room,
            organizer=self.user,
            title="b1",
            start_at=self._dt(day, time(10, 0)),
            end_at=self._dt(day, time(11, 0)),
        )
        b1.cancel()
        b1.save(update_fields=["status", "canceled_at", "updated_at"])

        b2 = RoomBooking(
            room=self.room,
            organizer=self.user,
            title="b2",
            start_at=self._dt(day, time(10, 30)),
            end_at=self._dt(day, time(11, 30)),
        )
        b2.full_clean()


class RoomAvailabilityServiceTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username="u1", password="pass12345")
        self.room = MeetingRoom.objects.create(name="A101", is_active=True)
        self.tz = timezone.get_current_timezone()

    def _dt(self, day: date, t: time) -> datetime:
        return timezone.make_aware(datetime.combine(day, t), timezone=self.tz)

    def test_room_free_slots_returns_complements(self):
        day = date(2026, 2, 15)
        RoomBooking.objects.create(
            room=self.room,
            organizer=self.user,
            title="b1",
            start_at=self._dt(day, time(10, 0)),
            end_at=self._dt(day, time(11, 0)),
        )
        RoomBooking.objects.create(
            room=self.room,
            organizer=self.user,
            title="b2",
            start_at=self._dt(day, time(13, 0)),
            end_at=self._dt(day, time(14, 0)),
        )

        slots = room_free_slots(room=self.room, day=day, day_start=time(9, 0), day_end=time(18, 0))
        got = [(s.start.time(), s.end.time()) for s in slots]
        expected = [(time(9, 0), time(10, 0)), (time(11, 0), time(13, 0)), (time(14, 0), time(18, 0))]
        self.assertEqual(got, expected)


class RoomBookingApiTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user1 = self.User.objects.create_user(username="u1", password="pass12345")
        self.user2 = self.User.objects.create_user(username="u2", password="pass12345")
        self.room = MeetingRoom.objects.create(name="A101", is_active=True)
        self.client = APIClient()
        self.tz = timezone.get_current_timezone()

    def _dt(self, day: date, t: time) -> datetime:
        return timezone.make_aware(datetime.combine(day, t), timezone=self.tz)

    def test_api_create_conflict_returns_400(self):
        day = date(2026, 2, 15)
        RoomBooking.objects.create(
            room=self.room,
            organizer=self.user1,
            title="b1",
            start_at=self._dt(day, time(10, 0)),
            end_at=self._dt(day, time(11, 0)),
        )

        self.client.force_authenticate(user=self.user1)
        resp = self.client.post(
            "/api/v1/room-bookings/",
            data={
                "room": self.room.id,
                "title": "b2",
                "start_at": self._dt(day, time(10, 30)).isoformat(),
                "end_at": self._dt(day, time(11, 30)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_api_cancel_not_owner_hidden(self):
        day = date(2026, 2, 15)
        booking = RoomBooking.objects.create(
            room=self.room,
            organizer=self.user1,
            title="b1",
            start_at=self._dt(day, time(10, 0)),
            end_at=self._dt(day, time(11, 0)),
        )

        self.client.force_authenticate(user=self.user2)
        resp = self.client.post(f"/api/v1/room-bookings/{booking.id}/cancel/")
        self.assertEqual(resp.status_code, 404)

