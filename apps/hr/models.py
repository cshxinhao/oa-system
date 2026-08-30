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
    
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Approver"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leaves_to_approve',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Reviewer"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leaves_to_review',
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
        # weekends do not count toward any leave type's duration
        from .services import count_working_days, is_weekend
        if self.pk and self.dates.exists():
            return sum(1 for d in self.dates.all() if not is_weekend(d.date))
        if not self.start_date or not self.end_date:
            return 0
        return count_working_days(self.start_date, self.end_date)

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

class LeaveQuota(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("User"),
        on_delete=models.CASCADE,
        related_name='leave_quotas',
    )
    year = models.PositiveSmallIntegerField(_("Year"))
    leave_type = models.CharField(
        _("Leave Type"),
        max_length=20,
        choices=LeaveApplication.TYPE_CHOICES,
        default=LeaveApplication.TYPE_ANNUAL,
    )
    total_days = models.DecimalField(
        _("Total Days"),
        max_digits=4,
        decimal_places=1,
        help_text=_("Leave entitlement for the year (half days allowed)."),
    )

    class Meta:
        verbose_name = _("Leave Quota")
        verbose_name_plural = _("Leave Quotas")
        ordering = ['user', '-year']
        constraints = [
            models.UniqueConstraint(fields=['user', 'year', 'leave_type'], name='unique_user_year_type_quota'),
        ]

    def __str__(self):
        return f"{self.user} {self.year} {self.get_leave_type_display()}: {self.total_days} days"

    @property
    def used_days(self):
        from .services import leave_used_days
        return leave_used_days(self.user, self.year, self.leave_type)

    @property
    def remaining_days(self):
        return self.total_days - self.used_days
