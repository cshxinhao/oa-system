from __future__ import annotations

from datetime import datetime, time, timedelta

from django import forms
from django.utils import timezone

from .models import MeetingRoom, RoomBooking


class RoomBookingForm(forms.ModelForm):
    booking_date = forms.DateField(
        label="Date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    start_time = forms.TimeField(
        label="Start Time",
        widget=forms.TimeInput(attrs={"type": "time", "step": 600, "class": "form-control"}),
    )
    end_time = forms.TimeField(
        label="End Time",
        widget=forms.TimeInput(attrs={"type": "time", "step": 600, "class": "form-control"}),
    )

    class Meta:
        model = RoomBooking
        fields = ["room", "title", "remarks", "guest_count"]
        widgets = {
            "room": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "guest_count": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate date/time from existing instance
        if self.instance and self.instance.start_at:
            tz = timezone.get_current_timezone()
            start = self.instance.start_at.astimezone(tz)
            self.fields["booking_date"].initial = start.date()
            self.fields["start_time"].initial = start.time()
        if self.instance and self.instance.end_at:
            tz = timezone.get_current_timezone()
            end = self.instance.end_at.astimezone(tz)
            self.fields["end_time"].initial = end.time()

    def clean(self):
        cleaned_data = super().clean()
        booking_date = cleaned_data.get("booking_date")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")
        room = cleaned_data.get("room")

        if booking_date and start_time and end_time:
            tz = timezone.get_current_timezone()
            start_at = timezone.make_aware(
                datetime.combine(booking_date, start_time), tz
            )
            end_at = timezone.make_aware(
                datetime.combine(booking_date, end_time), tz
            )

            if start_at >= end_at:
                self.add_error("end_time", "End time must be later than start time")
                return cleaned_data

            cleaned_data["start_at"] = start_at
            cleaned_data["end_at"] = end_at

            if room:
                guest_count = cleaned_data.get("guest_count", 0)
                if guest_count is not None and room.capacity and guest_count > room.capacity:
                    self.add_error(
                        "guest_count",
                        f"The number of guests ({guest_count}) exceeds the room capacity ({room.capacity}).",
                    )

                conflict_exists = (
                    RoomBooking.objects.filter(room=room, status=RoomBooking.STATUS_BOOKED)
                    .exclude(pk=self.instance.pk)
                    .filter(start_at__lt=end_at, end_at__gt=start_at)
                    .exists()
                )
                if conflict_exists:
                    self.add_error(None, "The meeting room is already booked for the selected time slot")

        return cleaned_data


class RoomWindowAvailabilityForm(forms.Form):
    start_at = forms.DateTimeField(
        label="Start Time",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
    )
    end_at = forms.DateTimeField(
        label="End Time",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")

        if (start_at and not end_at) or (end_at and not start_at):
            raise forms.ValidationError("Please provide both start and end times")

        if start_at and end_at and start_at >= end_at:
            self.add_error("end_at", "End time must be later than start time")

        return cleaned_data


class RoomDayFreeSlotsForm(forms.Form):
    room = forms.ModelChoiceField(
        label="Meeting Room",
        required=False,
        queryset=MeetingRoom.objects.filter(is_active=True).order_by("name"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date = forms.DateField(
        label="Date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    day_start = forms.TimeField(
        label="Day Start",
        required=False,
        initial=time(9, 0),
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )
    day_end = forms.TimeField(
        label="Day End",
        required=False,
        initial=time(18, 0),
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get("room")
        selected_date = cleaned_data.get("date")
        day_start = cleaned_data.get("day_start")
        day_end = cleaned_data.get("day_end")

        if (room and not selected_date) or (selected_date and not room):
            raise forms.ValidationError("Please select both meeting room and date")

        if day_start and day_end and day_start >= day_end:
            self.add_error("day_end", "Day end time must be later than day start time")

        return cleaned_data


class BookedRoomsFilterForm(forms.Form):
    start_date = forms.DateField(
        label="Start Date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    end_date = forms.DateField(
        label="End Date",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.now().date()
        self.fields["start_date"].initial = today
        self.fields["end_date"].initial = today

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if (start_date and not end_date) or (end_date and not start_date):
            raise forms.ValidationError("Please provide both start and end dates")

        if start_date and end_date and start_date > end_date:
            self.add_error("end_date", "End date must not be earlier than start date")

        return cleaned_data
