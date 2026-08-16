from django.conf import settings
from django.db import models
import uuid


class FieldType(models.TextChoices):
    TEXT = 'text', 'Text'
    TEXTAREA = 'textarea', 'Text Area'
    NUMBER = 'number', 'Number'
    CHECKBOX = 'checkbox', 'Checkbox'
    SELECT = 'select', 'Select'
    MULTI_SELECT = 'multi_select', 'Multi Select'
    DATE = 'date', 'Date'
    TIME = 'time', 'Time'
    FILE = 'file', 'File Upload'


class CustomReportTemplate(models.Model):
    """
    Dynamic custom report template created by admin.
    Existing fixed reports in the reports app are intentionally separate.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive custom reports will not appear to employees or be selectable for jobs."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    class Meta:
        verbose_name = 'Custom Report Template'
        verbose_name_plural = 'Custom Report Templates'
        ordering = ['name']


class CustomReportField(models.Model):
    """A dynamic field belonging to a custom report template."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        CustomReportTemplate,
        on_delete=models.CASCADE,
        related_name='fields'
    )
    label = models.CharField(max_length=200)
    field_type = models.CharField(
        max_length=20,
        choices=FieldType.choices,
        default=FieldType.TEXT
    )
    options = models.TextField(
        blank=True,
        help_text="Comma-separated options for select/multi-select fields."
    )
    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    helper_text = models.CharField(max_length=300, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def options_list(self):
        if not self.options:
            return []
        return [opt.strip() for opt in self.options.split(',') if opt.strip()]

    def __str__(self):
        return f"[{self.template.name}] {self.label} ({self.field_type})"

    class Meta:
        verbose_name = 'Custom Report Field'
        verbose_name_plural = 'Custom Report Fields'
        ordering = ['order', 'created_at']
        unique_together = [['template', 'order']]


class CustomReportSubmission(models.Model):
    """One locked submission per employee per custom report template per job."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        'jobs.Job',
        on_delete=models.CASCADE,
        related_name='custom_report_submissions'
    )
    template = models.ForeignKey(
        CustomReportTemplate,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='custom_report_submissions'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.template.name} - {self.job.job_id} - {self.employee}"

    class Meta:
        verbose_name = 'Custom Report Submission'
        verbose_name_plural = 'Custom Report Submissions'
        unique_together = [['job', 'template', 'employee']]
        ordering = ['-submitted_at']


class CustomReportResponse(models.Model):
    """One response per field per custom report submission."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        CustomReportSubmission,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    field = models.ForeignKey(
        CustomReportField,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    value = models.TextField(blank=True)
    file = models.FileField(
        upload_to='custom_reports/uploads/',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.field.label}: {self.value or '[file]'}"

    class Meta:
        verbose_name = 'Custom Report Response'
        verbose_name_plural = 'Custom Report Responses'
        unique_together = [['submission', 'field']]
