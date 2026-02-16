from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import MeetingRoom, RoomBooking
from .permissions import IsStaffOrBookingOwner, IsStaffOrReadOnly
from .serializers import (
    AvailabilityWindowQuerySerializer,
    FreeSlotsQuerySerializer,
    MeetingRoomSerializer,
    RoomBookingSerializer,
)
from .services import available_rooms, room_free_slots


class MeetingRoomViewSet(viewsets.ModelViewSet):
    queryset = MeetingRoom.objects.all()
    serializer_class = MeetingRoomSerializer
    permission_classes = [IsStaffOrReadOnly]
    filterset_fields = ["is_active"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset

    @action(detail=False, methods=["get"], url_path="available", permission_classes=[IsAuthenticated])
    def available(self, request):
        query = AvailabilityWindowQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        rooms = available_rooms(query.validated_data["start_at"], query.validated_data["end_at"])
        serializer = self.get_serializer(rooms, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="free-slots", permission_classes=[IsAuthenticated])
    def free_slots(self, request, pk=None):
        room = self.get_object()
        query = FreeSlotsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)

        slots = room_free_slots(
            room=room,
            day=query.validated_data["date"],
            day_start=query.validated_data["day_start"],
            day_end=query.validated_data["day_end"],
        )
        return Response([{"start": s.start, "end": s.end} for s in slots])


class RoomBookingViewSet(viewsets.ModelViewSet):
    queryset = RoomBooking.objects.select_related("room", "organizer")
    serializer_class = RoomBookingSerializer
    permission_classes = [IsAuthenticated, IsStaffOrBookingOwner]
    filterset_fields = ["room", "status", "start_at", "end_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(organizer=self.request.user)

    def perform_create(self, serializer):
        validated = dict(serializer.validated_data)
        try:
            booking = RoomBooking(
                organizer=self.request.user,
                status=RoomBooking.STATUS_BOOKED,
                **validated,
            )
            booking.full_clean()
            booking.save()
            serializer.instance = booking
        except DjangoValidationError as exc:
            raise ValidationError(exc.message_dict or exc.messages)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        booking: RoomBooking = self.get_object()
        if booking.status != RoomBooking.STATUS_BOOKED:
            raise ValidationError("该预订状态已变更，无法取消")
        booking.cancel()
        booking.save(update_fields=["status", "canceled_at", "updated_at"])
        return Response(self.get_serializer(booking).data, status=status.HTTP_200_OK)
