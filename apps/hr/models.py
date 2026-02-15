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
        (STATUS_DRAFT, _('草稿')),
        (STATUS_PENDING, _('待审批')),
        (STATUS_APPROVED, _('已批准')),
        (STATUS_REJECTED, _('已拒绝')),
    )

    TYPE_SICK = 'sick'
    TYPE_ANNUAL = 'annual'
    TYPE_PERSONAL = 'personal'
    
    TYPE_CHOICES = (
        (TYPE_SICK, _('病假')),
        (TYPE_ANNUAL, _('年假')),
        (TYPE_PERSONAL, _('事假')),
    )

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name=_("申请人"), 
        on_delete=models.CASCADE,
        related_name='leave_applications'
    )
    leave_type = models.CharField(_("请假类型"), max_length=20, choices=TYPE_CHOICES, default=TYPE_SICK)
    start_date = models.DateField(_("开始日期"))
    end_date = models.DateField(_("结束日期"))
    reason = models.TextField(_("请假事由"))
    
    status = FSMField(_("状态"), default=STATUS_DRAFT, choices=STATUS_CHOICES, protected=True)
    
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("审批人"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leaves_to_review'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("请假申请")
        verbose_name_plural = _("请假申请")
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
