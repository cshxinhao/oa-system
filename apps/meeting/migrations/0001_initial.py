from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MeetingRoom",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=100, unique=True, verbose_name="会议室名称"
                    ),
                ),
                (
                    "location",
                    models.CharField(blank=True, max_length=200, verbose_name="位置"),
                ),
                (
                    "capacity",
                    models.PositiveIntegerField(default=0, verbose_name="容纳人数"),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="可用")),
                ("description", models.TextField(blank=True, verbose_name="描述")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "会议室",
                "verbose_name_plural": "会议室",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="RoomBooking",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(max_length=200, verbose_name="主题")),
                ("start_at", models.DateTimeField(verbose_name="开始时间")),
                ("end_at", models.DateTimeField(verbose_name="结束时间")),
                (
                    "status",
                    models.CharField(
                        choices=[("booked", "已预订"), ("canceled", "已取消")],
                        default="booked",
                        max_length=20,
                        verbose_name="状态",
                    ),
                ),
                (
                    "canceled_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="取消时间"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "organizer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="room_bookings",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="发起人",
                    ),
                ),
                (
                    "room",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bookings",
                        to="meeting.meetingroom",
                        verbose_name="会议室",
                    ),
                ),
            ],
            options={
                "verbose_name": "会议室预订",
                "verbose_name_plural": "会议室预订",
                "ordering": ["-start_at"],
                "indexes": [
                    models.Index(
                        fields=["room", "status", "start_at", "end_at"],
                        name="meeting_roo_room_id_2a72cf_idx",
                    ),
                    models.Index(
                        fields=["organizer", "status", "start_at"],
                        name="meeting_roo_organiz_e917cf_idx",
                    ),
                ],
            },
        ),
    ]
