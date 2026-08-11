from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, ListView, TemplateView, View

from itertools import groupby

from .forms import BookedRoomsFilterForm, RoomBookingForm, RoomDayFreeSlotsForm
from .models import MeetingRoom, RoomBooking
from .services import room_free_slots


class BookingListView(LoginRequiredMixin, ListView):
    model = RoomBooking
    template_name = "meeting/booking_list.html"
    context_object_name = "bookings"

    def get_queryset(self):
        user = self.request.user
        queryset = (
            RoomBooking.objects.filter(
                organizer=user,
                end_at__date__gte=timezone.now().date(),
            )
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
        return initial

    def form_valid(self, form):
        form.instance.organizer = self.request.user
        form.instance.status = RoomBooking.STATUS_BOOKED
        form.instance.start_at = form.cleaned_data.get("start_at")
        form.instance.end_at = form.cleaned_data.get("end_at")
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


class MeetingRoomListView(LoginRequiredMixin, ListView):
    model = MeetingRoom
    template_name = "meeting/room_list.html"
    context_object_name = "rooms"

    def get_queryset(self):
        return MeetingRoom.objects.filter(is_active=True).order_by("name")


class RoomAvailabilityView(LoginRequiredMixin, TemplateView):
    template_name = "meeting/availability.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        slots_form = RoomDayFreeSlotsForm(self.request.GET or None)
        context["slots_form"] = slots_form

        context["free_slots"] = []
        context["free_slots_room"] = None
        context["slots_searched"] = False

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

        return context


class BookedRoomsView(LoginRequiredMixin, TemplateView):
    template_name = "meeting/booked_rooms.html"

    def _get_all_bookings(self):
        return (
            RoomBooking.objects.filter(
                status=RoomBooking.STATUS_BOOKED,
                end_at__date__gte=timezone.now().date(),
            )
            .select_related("room", "organizer")
            .order_by("room__name", "start_at")
        )

    def _group_by_room(self, bookings):
        return [
            {"room": room, "bookings": list(room_bookings)}
            for room, room_bookings in groupby(bookings, key=lambda b: b.room)
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        has_params = bool(self.request.GET)
        form = BookedRoomsFilterForm(self.request.GET or None)
        context["form"] = form
        context["searched"] = False
        context["booked_groups"] = []

        if has_params and form.is_valid():
            start_date = form.cleaned_data.get("start_date")
            end_date = form.cleaned_data.get("end_date")
            if start_date and end_date:
                context["searched"] = True
                bookings = (
                    RoomBooking.objects.filter(
                        status=RoomBooking.STATUS_BOOKED,
                        start_at__date__lte=end_date,
                        end_at__date__gte=start_date,
                    )
                    .select_related("room", "organizer")
                    .order_by("room__name", "start_at")
                )
                context["booked_groups"] = self._group_by_room(bookings)
        elif not has_params:
            # First visit: show all booked rooms
            context["booked_groups"] = self._group_by_room(self._get_all_bookings())

        return context
