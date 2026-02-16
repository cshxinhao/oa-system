from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, TemplateView, View

from .forms import RoomBookingForm, RoomDayFreeSlotsForm, RoomWindowAvailabilityForm
from .models import MeetingRoom, RoomBooking
from .services import available_rooms, room_free_slots


class BookingListView(LoginRequiredMixin, ListView):
    model = RoomBooking
    template_name = "meeting/booking_list.html"
    context_object_name = "bookings"

    def get_queryset(self):
        user = self.request.user
        queryset = (
            RoomBooking.objects.filter(organizer=user)
            .select_related("room", "organizer")
            .order_by("-start_at")
        )
        return queryset


class BookingCreateView(LoginRequiredMixin, CreateView):
    model = RoomBooking
    form_class = RoomBookingForm
    template_name = "meeting/booking_form.html"
    success_url = reverse_lazy("meeting:booking_list")

    def get_initial(self):
        initial = super().get_initial()
        room_id = self.request.GET.get("room")
        if room_id:
            initial["room"] = room_id
        start_at = self.request.GET.get("start_at")
        end_at = self.request.GET.get("end_at")
        if start_at:
            initial["start_at"] = start_at
        if end_at:
            initial["end_at"] = end_at
        return initial

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        form.instance.status = RoomBooking.STATUS_BOOKED
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.full_clean()
                self.object.save()
        except Exception:
            if not form.errors:
                form.add_error(None, "预订失败，请检查填写内容后重试")
            return self.form_invalid(form)
        messages.success(self.request, "会议室预订成功")
        return redirect(self.success_url)


class BookingCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        booking = get_object_or_404(RoomBooking.objects.select_related("organizer"), pk=pk)
        if not (request.user.is_staff or booking.organizer_id == request.user.id):
            raise PermissionDenied("您没有权限取消该预订")

        if booking.status != RoomBooking.STATUS_BOOKED:
            messages.warning(request, "该预订状态已变更，无法取消")
            return redirect("meeting:booking_list")

        with transaction.atomic():
            booking.cancel()
            booking.save(update_fields=["status", "canceled_at", "updated_at"])

        messages.success(request, "已取消预订")
        return redirect("meeting:booking_list")


class RoomAvailabilityView(LoginRequiredMixin, TemplateView):
    template_name = "meeting/availability.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        window_form = RoomWindowAvailabilityForm(self.request.GET or None)
        slots_form = RoomDayFreeSlotsForm(self.request.GET or None)

        context["window_form"] = window_form
        context["slots_form"] = slots_form

        context["available_rooms"] = []
        context["free_slots"] = []
        context["free_slots_room"] = None
        context["window_searched"] = False
        context["slots_searched"] = False

        if window_form.is_valid():
            start_at = window_form.cleaned_data.get("start_at")
            end_at = window_form.cleaned_data.get("end_at")
            if start_at and end_at:
                context["window_searched"] = True
                context["available_rooms"] = available_rooms(start_at, end_at)

        if slots_form.is_valid():
            room = slots_form.cleaned_data.get("room")
            selected_date = slots_form.cleaned_data.get("date")
            day_start = slots_form.cleaned_data.get("day_start")
            day_end = slots_form.cleaned_data.get("day_end")
            if room and selected_date and day_start and day_end:
                context["slots_searched"] = True
                context["free_slots_room"] = room
                context["free_slots"] = room_free_slots(
                    room=room,
                    day=selected_date,
                    day_start=day_start,
                    day_end=day_end,
                )

        context["rooms"] = MeetingRoom.objects.filter(is_active=True).order_by("name")
        return context
