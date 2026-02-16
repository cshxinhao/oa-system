from __future__ import annotations

from datetime import time

from django import forms

from .models import MeetingRoom, RoomBooking


class RoomBookingForm(forms.ModelForm):
    class Meta:
        model = RoomBooking
        fields = ["room", "title", "start_at", "end_at"]
        widgets = {
            "room": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")
        room = cleaned_data.get("room")

        if start_at and end_at and start_at >= end_at:
            self.add_error("end_at", "结束时间必须晚于开始时间")
            return cleaned_data

        if room and start_at and end_at:
            conflict_exists = (
                RoomBooking.objects.filter(room=room, status=RoomBooking.STATUS_BOOKED)
                .exclude(pk=self.instance.pk)
                .filter(start_at__lt=end_at, end_at__gt=start_at)
                .exists()
            )
            if conflict_exists:
                self.add_error(None, "该会议室在所选时间段已被占用")
        return cleaned_data


class RoomWindowAvailabilityForm(forms.Form):
    start_at = forms.DateTimeField(
        label="开始时间",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
    )
    end_at = forms.DateTimeField(
        label="结束时间",
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-control"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        start_at = cleaned_data.get("start_at")
        end_at = cleaned_data.get("end_at")

        if (start_at and not end_at) or (end_at and not start_at):
            raise forms.ValidationError("请同时填写开始时间与结束时间")

        if start_at and end_at and start_at >= end_at:
            self.add_error("end_at", "结束时间必须晚于开始时间")

        return cleaned_data


class RoomDayFreeSlotsForm(forms.Form):
    room = forms.ModelChoiceField(
        label="会议室",
        required=False,
        queryset=MeetingRoom.objects.filter(is_active=True).order_by("name"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date = forms.DateField(
        label="日期",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    day_start = forms.TimeField(
        label="日开始",
        required=False,
        initial=time(9, 0),
        widget=forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
    )
    day_end = forms.TimeField(
        label="日结束",
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
            raise forms.ValidationError("请同时选择会议室与日期")

        if day_start and day_end and day_start >= day_end:
            self.add_error("day_end", "日结束时间必须晚于日开始时间")

        return cleaned_data
