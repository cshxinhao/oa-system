from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, Sequence

from django.db.models import Q
from django.utils import timezone

from .models import MeetingRoom, RoomBooking


@dataclass(frozen=True)
class TimeRange:
    start: datetime
    end: datetime


def _merge_ranges(ranges: Sequence[TimeRange]) -> list[TimeRange]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda r: r.start)
    merged: list[TimeRange] = [sorted_ranges[0]]
    for current in sorted_ranges[1:]:
        last = merged[-1]
        if current.start <= last.end:
            merged[-1] = TimeRange(start=last.start, end=max(last.end, current.end))
        else:
            merged.append(current)
    return merged


def _invert_ranges(window: TimeRange, busy: Sequence[TimeRange]) -> list[TimeRange]:
    if window.start >= window.end:
        return []
    merged_busy = _merge_ranges([r for r in busy if r.start < window.end and r.end > window.start])

    cursor = window.start
    free: list[TimeRange] = []
    for b in merged_busy:
        start = max(window.start, b.start)
        end = min(window.end, b.end)
        if cursor < start:
            free.append(TimeRange(start=cursor, end=start))
        cursor = max(cursor, end)
    if cursor < window.end:
        free.append(TimeRange(start=cursor, end=window.end))
    return free


def available_rooms(start_at: datetime, end_at: datetime) -> "MeetingRoom.QuerySet":
    overlapping_bookings = RoomBooking.objects.filter(
        status=RoomBooking.STATUS_BOOKED,
        start_at__lt=end_at,
        end_at__gt=start_at,
    ).values_list("room_id", flat=True)
    return MeetingRoom.objects.filter(is_active=True).exclude(id__in=overlapping_bookings).order_by("name")


def room_free_slots(
    *,
    room: MeetingRoom,
    day: date,
    day_start: time,
    day_end: time,
) -> list[TimeRange]:
    tz = timezone.get_current_timezone()
    window_start = timezone.make_aware(datetime.combine(day, day_start), timezone=tz)
    window_end = timezone.make_aware(datetime.combine(day, day_end), timezone=tz)
    window = TimeRange(start=window_start, end=window_end)

    bookings = (
        RoomBooking.objects.filter(
            room=room,
            status=RoomBooking.STATUS_BOOKED,
        )
        .filter(Q(start_at__lt=window_end) & Q(end_at__gt=window_start))
        .only("start_at", "end_at")
        .order_by("start_at")
    )
    busy = [
        TimeRange(
            start=timezone.localtime(b.start_at, timezone=tz),
            end=timezone.localtime(b.end_at, timezone=tz),
        )
        for b in bookings
    ]
    free = _invert_ranges(window, busy)
    return [
        TimeRange(
            start=timezone.localtime(s.start, timezone=tz),
            end=timezone.localtime(s.end, timezone=tz),
        )
        for s in free
    ]
