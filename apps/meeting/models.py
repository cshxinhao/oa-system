from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class MeetingRoom(models.Model):
    name = models.CharField(_("Room Name"), max_length=100, unique=True)
    location = models.CharField(_("Location"), max_length=200, blank=True)
    capacity = models.PositiveIntegerField(_("Capacity"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)
    description = models.TextField(_("Description"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Meeting Room")
        verbose_name_plural = _("Meeting Rooms")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class RoomBooking(models.Model):
    STATUS_BOOKED = "booked"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_BOOKED, _("Booked")),
        (STATUS_CANCELED, _("Canceled")),
    ]

    room = models.ForeignKey(
        MeetingRoom,
        verbose_name=_("Meeting Room"),
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Organizer"),
        on_delete=models.PROTECT,
        related_name="room_bookings",
    )
    title = models.CharField(_("Title"), max_length=200)
    start_at = models.DateTimeField(_("Start Time"))
    end_at = models.DateTimeField(_("End Time"))
    status = models.CharField(_("Status"), max_length=20, choices=STATUS_CHOICES, default=STATUS_BOOKED)
    canceled_at = models.DateTimeField(_("Canceled At"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Room Booking")
        verbose_name_plural = _("Room Bookings")
        ordering = ["-start_at"]
        indexes = [
            models.Index(fields=["room", "status", "start_at", "end_at"]),
            models.Index(fields=["organizer", "status", "start_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.room} - {self.title} ({self.start_at}~{self.end_at})"

    def clean(self) -> None:
        errors: dict[str, list[str]] = {}

        if self.start_at and self.end_at and self.start_at >= self.end_at:
            errors.setdefault("end_at", []).append("End time must be later than start time")

        if self.room_id and hasattr(self, "room") and not self.room.is_active:
            errors.setdefault("room", []).append("This meeting room is currently inactive")

        if self.status == self.STATUS_BOOKED and self.room_id and self.start_at and self.end_at:
            if self.conflicting_bookings().exists():
                errors.setdefault("__all__", []).append("The meeting room is already booked for the selected time slot")

        if errors:
            raise ValidationError(errors)

    def conflicting_bookings(self) -> "models.QuerySet[RoomBooking]":
        return (
            RoomBooking.objects.filter(room_id=self.room_id, status=self.STATUS_BOOKED)
            .exclude(pk=self.pk)
            .filter(start_at__lt=self.end_at, end_at__gt=self.start_at)
        )

    def cancel(self) -> None:
        if self.status == self.STATUS_CANCELED:
            return
        self.status = self.STATUS_CANCELED
        self.canceled_at = timezone.now()

