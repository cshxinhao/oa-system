from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Document(models.Model):
    title = models.CharField(_("Title"), max_length=200)
    file = models.FileField(_("File"), upload_to='docs/%Y/%m/')
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name=_("Uploader"), 
        on_delete=models.CASCADE
    )
    description = models.TextField(_("Description"), blank=True)
    is_public = models.BooleanField(_("Public"), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Document")
        verbose_name_plural = _("Document Management")
        ordering = ['-created_at']

    def __str__(self):
        return self.title
