from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class Department(models.Model):
    name = models.CharField(_("Department Name"), max_length=100)
    parent = models.ForeignKey(
        "self", 
        verbose_name=_("Parent Department"), 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="children"
    )
    manager = models.ForeignKey(
        "core.User", 
        verbose_name=_("Department Manager"), 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="managed_departments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Department")
        verbose_name_plural = _("Departments")

    def __str__(self):
        return self.name

class User(AbstractUser):
    employee_id = models.CharField(_("Employee ID"), max_length=20, unique=True, null=True, blank=True)
    department = models.ForeignKey(
        Department, 
        verbose_name=_("Department"), 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="members"
    )
    position = models.CharField(_("Position"), max_length=100, blank=True)
    phone = models.CharField(_("Phone"), max_length=20, blank=True)
    can_approve_all_leaves = models.BooleanField(
        _("Can Approve All Leaves"),
        default=False,
        help_text=_("Global approver: appears in every employee's approver picker and can approve all leave applications."),
    )

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return f"{self.username} ({self.get_full_name() or self.username})"
