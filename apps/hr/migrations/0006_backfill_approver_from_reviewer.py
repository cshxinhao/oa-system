from django.db import migrations
from django.db.models import F


def backfill_approver(apps, schema_editor):
    # Historical applications: the old reviewer recorded who actually processed
    # the application, which becomes the initial approver value. The reviewer
    # column itself is kept untouched.
    LeaveApplication = apps.get_model('hr', 'LeaveApplication')
    LeaveApplication.objects.update(approver=F('reviewer'))


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0005_leaveapplication_approver_leavequota_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_approver, migrations.RunPython.noop),
    ]
