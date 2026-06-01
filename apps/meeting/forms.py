from __future__ import annotations

from datetime import time

from django import forms

from .models import MeetingRoom, RoomBooking


class RoomBookingForm(forms.ModelForm):
    class Meta:
        model = RoomBooking
        fields = ["room", "title", "start_at", "end_at", "remarks", "guest_count"]
        widgets = {
            "room": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "remarks": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "guest_count": forms.NumberInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")
        room = cleaned_data.get("room")

        if start_at and end_at and start_at >= end_at:
            self.add_error("end_at", "End time must be later than start time")
            return cleaned_data

        if room and start_at and end_at:
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
