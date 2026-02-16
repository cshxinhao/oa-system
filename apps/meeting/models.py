from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class MeetingRoom(models.Model):
    name = models.CharField(_("会议室名称"), max_length=100, unique=True)
    location = models.CharField(_("位置"), max_length=200, blank=True)
    capacity = models.PositiveIntegerField(_("容纳人数"), default=0)
    is_active = models.BooleanField(_("可用"), default=True)
    description = models.TextField(_("描述"), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("会议室")
        verbose_name_plural = _("会议室")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class RoomBooking(models.Model):
    STATUS_BOOKED = "booked"
    STATUS_CANCELED = "canceled"
    STATUS_CHOICES = [
        (STATUS_BOOKED, _("已预订")),
        (STATUS_CANCELED, _("已取消")),
    ]

    room = models.ForeignKey(
        MeetingRoom,
        verbose_name=_("会议室"),
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("发起人"),
        on_delete=models.PROTECT,
        related_name="room_bookings",
    )
    title = models.CharField(_("主题"), max_length=200)
    start_at = models.DateTimeField(_("开始时间"))
    end_at = models.DateTimeField(_("结束时间"))
    status = models.CharField(_("状态"), max_length=20, choices=STATUS_CHOICES, default=STATUS_BOOKED)
    canceled_at = models.DateTimeField(_("取消时间"), null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("会议室预订")
        verbose_name_plural = _("会议室预订")
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
            errors.setdefault("end_at", []).append("结束时间必须晚于开始时间")

        if self.room_id and hasattr(self, "room") and not self.room.is_active:
            errors.setdefault("room", []).append("该会议室当前不可用")

        if self.status == self.STATUS_BOOKED and self.room_id and self.start_at and self.end_at:
            if self.conflicting_bookings().exists():
                errors.setdefault("__all__", []).append("该会议室在所选时间段已被占用")

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

