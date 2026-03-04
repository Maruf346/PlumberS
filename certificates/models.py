from django.db import models
from django.conf import settings
import uuid


class Certificate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='certificates'
    )
    name = models.CharField(max_length=200)
    issuing_organization = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    issue_date = models.DateField()
    expiration_date = models.DateField(null=True, blank=True)
    media = models.FileField(upload_to='certificates/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date']
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'

    def __str__(self):
        return f"{self.name} — {self.user.email}"