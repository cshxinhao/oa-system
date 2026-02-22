from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django_fsm import FSMField, transition

class LeaveApplication(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = (
        (STATUS_DRAFT, _('Draft')),
        (STATUS_PENDING, _('Pending')),
        (STATUS_APPROVED, _('Approved')),
        (STATUS_REJECTED, _('Rejected')),
    )

    TYPE_SICK = 'sick'
    TYPE_ANNUAL = 'annual'
    TYPE_PERSONAL = 'personal'
    
    TYPE_CHOICES = (
        (TYPE_SICK, _('Sick Leave')),
        (TYPE_ANNUAL, _('Annual Leave')),
        (TYPE_PERSONAL, _('Personal Leave')),
    )

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name=_("Applicant"), 
        on_delete=models.CASCADE,
        related_name='leave_applications'
    )
    leave_type = models.CharField(_("Leave Type"), max_length=20, choices=TYPE_CHOICES, default=TYPE_SICK)
    start_date = models.DateField(_("Start Date"))
    end_date = models.DateField(_("End Date"))
    reason = models.TextField(_("Reason"))
    
    status = FSMField(_("Status"), default=STATUS_DRAFT, choices=STATUS_CHOICES, protected=True)
    
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Reviewer"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leaves_to_review'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Leave Application")
        verbose_name_plural = _("Leave Applications")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.applicant} - {self.get_leave_type_display()} ({self.start_date})"

    @property
    def duration_days(self):
        if not self.start_date or not self.end_date:
            return 0
        return (self.end_date - self.start_date).days + 1

    @transition(field=status, source=STATUS_DRAFT, target=STATUS_PENDING)
    def submit(self):
        """提交申请"""
        pass

    @transition(field=status, source=STATUS_PENDING, target=STATUS_APPROVED)
    def approve(self):
        """批准"""
        pass

    @transition(field=status, source=STATUS_PENDING, target=STATUS_REJECTED)
    def reject(self):
        """拒绝"""
        pass
