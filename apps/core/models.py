from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

class Department(models.Model):
    name = models.CharField(_("部门名称"), max_length=100)
    parent = models.ForeignKey(
        "self", 
        verbose_name=_("上级部门"), 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="children"
    )
    manager = models.ForeignKey(
        "core.User", 
        verbose_name=_("部门负责人"), 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="managed_departments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("部门")
        verbose_name_plural = _("部门")

    def __str__(self):
        return self.name

class User(AbstractUser):
    employee_id = models.CharField(_("工号"), max_length=20, unique=True, null=True, blank=True)
    department = models.ForeignKey(
        Department, 
        verbose_name=_("所属部门"), 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="members"
    )
    position = models.CharField(_("职位"), max_length=100, blank=True)
    phone = models.CharField(_("手机号"), max_length=20, blank=True)
    
    class Meta:
        verbose_name = _("用户")
        verbose_name_plural = _("用户")

    def __str__(self):
        return f"{self.username} ({self.get_full_name() or self.username})"
