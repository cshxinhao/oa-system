from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Notice(models.Model):
    title = models.CharField(_("Title"), max_length=200)
    content = models.TextField(_("Content"))
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name=_("Author"), 
        on_delete=models.CASCADE
    )
    published_at = models.DateTimeField(_("Published At"), auto_now_add=True)
    is_published = models.BooleanField(_("Published"), default=True)

    class Meta:
        verbose_name = _("Notice")
        verbose_name_plural = _("Notices")
        ordering = ['-published_at']

    def __str__(self):
        return self.title
