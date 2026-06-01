from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django_fsm import FSMField, transition

class LeaveApplication(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_WITHDRAWN = 'withdrawn'

    STATUS_CHOICES = (
        (STATUS_DRAFT, _('Draft')),
        (STATUS_PENDING, _('Pending')),
        (STATUS_APPROVED, _('Approved')),
        (STATUS_REJECTED, _('Rejected')),
        (STATUS_WITHDRAWN, _('Withdrawn')),
    )

    TYPE_SICK = 'sick'
    TYPE_ANNUAL = 'annual'
    TYPE_BIRTHDAY = 'birthday'
    TYPE_MATERNITY = 'maternity'
    TYPE_PATERNITY = 'paternity'
    TYPE_COMPASSIONATE = 'compassionate'
    TYPE_NO_PAY = 'no_pay'
    
    TYPE_CHOICES = (
        (TYPE_SICK, _('Sick Leave')),
        (TYPE_ANNUAL, _('Annual Leave')),
        (TYPE_BIRTHDAY, _('Birthday Leave')),
        (TYPE_MATERNITY, _('Maternity Leave')),
        (TYPE_PATERNITY, _('Paternity Leave')),
        (TYPE_COMPASSIONATE, _('Compassionate Leave')),
        (TYPE_NO_PAY, _('No Pay Leave')),
    )

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name=_("Applicant"), 
        on_delete=models.CASCADE,
        related_name='leave_applications'
    )
    leave_type = models.CharField(_("Leave Type"), max_length=20, choices=TYPE_CHOICES, default=TYPE_SICK)
    is_half_day = models.BooleanField(_("Half Day"), default=False)
    HALF_DAY_AM = "am"
    HALF_DAY_PM = "pm"
    HALF_DAY_PERIOD_CHOICES = (
        (HALF_DAY_AM, _("AM")),
        (HALF_DAY_PM, _("PM")),
    )
    half_day_period = models.CharField(
        _("Half Day Period"),
        max_length=2,
        choices=HALF_DAY_PERIOD_CHOICES,
        null=True,
        blank=True,
    )
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
        if self.is_half_day:
            return 0.5
        if self.pk and self.dates.exists():
            return self.dates.count()
        if not self.start_date or not self.end_date:
            return 0
        return (self.end_date - self.start_date).days + 1

    @property
    def expected_approver(self):
        applicant = self.applicant
        dept = getattr(applicant, "department", None)
        if not dept or not dept.manager:
            return None
        if dept.manager != applicant:
            return dept.manager
        if dept.parent and dept.parent.manager:
            return dept.parent.manager
        return None

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

    @transition(field=status, source=STATUS_PENDING, target=STATUS_WITHDRAWN)
    def withdraw(self):
        """撤回"""
        pass

class LeaveApplicationDate(models.Model):
    application = models.ForeignKey(LeaveApplication, on_delete=models.CASCADE, related_name='dates')
    date = models.DateField()
    
    class Meta:
        ordering = ['date']

    def __str__(self):
        return str(self.date)
