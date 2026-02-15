from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Notice(models.Model):
    title = models.CharField(_("标题"), max_length=200)
    content = models.TextField(_("内容"))
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name=_("发布人"), 
        on_delete=models.CASCADE
    )
    published_at = models.DateTimeField(_("发布时间"), auto_now_add=True)
    is_published = models.BooleanField(_("是否发布"), default=True)

    class Meta:
        verbose_name = _("公告")
        verbose_name_plural = _("公告")
        ordering = ['-published_at']

    def __str__(self):
        return self.title
