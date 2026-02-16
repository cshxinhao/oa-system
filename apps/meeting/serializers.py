from rest_framework import serializers

from .models import MeetingRoom, RoomBooking


class MeetingRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingRoom
        fields = ["id", "name", "location", "capacity", "is_active", "description"]


class RoomBookingSerializer(serializers.ModelSerializer):
    room_name = serializers.CharField(source="room.name", read_only=True)

    class Meta:
        model = RoomBooking
        fields = [
            "id",
            "room",
            "room_name",
            "organizer",
            "title",
            "start_at",
            "end_at",
            "status",
            "canceled_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["organizer", "status", "canceled_at", "created_at", "updated_at"]


class AvailabilityWindowQuerySerializer(serializers.Serializer):
    start_at = serializers.DateTimeField()
    end_at = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["start_at"] >= attrs["end_at"]:
            raise serializers.ValidationError("end_at 必须晚于 start_at")
        return attrs


class FreeSlotsQuerySerializer(serializers.Serializer):
    date = serializers.DateField()
    day_start = serializers.TimeField(required=False, default="09:00")
    day_end = serializers.TimeField(required=False, default="18:00")

    def validate(self, attrs):
        if attrs["day_start"] >= attrs["day_end"]:
            raise serializers.ValidationError("day_end 必须晚于 day_start")
        return attrs

