from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Document(models.Model):
    title = models.CharField(_("文档标题"), max_length=200)
    file = models.FileField(_("文件"), upload_to='docs/%Y/%m/')
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        verbose_name=_("上传人"), 
        on_delete=models.CASCADE
    )
    description = models.TextField(_("描述"), blank=True)
    is_public = models.BooleanField(_("全员可见"), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("文档")
        verbose_name_plural = _("文档管理")
        ordering = ['-created_at']

    def __str__(self):
        return self.title
