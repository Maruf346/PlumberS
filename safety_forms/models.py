from django.db import models
import uuid
from django.conf import settings


class FieldType(models.TextChoices):
    TEXT = 'text', 'Text'                        # single line text input
    TEXTAREA = 'textarea', 'Text Area'           # multi-line text input
    NUMBER = 'number', 'Number'                  # numeric input
    CHECKBOX = 'checkbox', 'Checkbox'            # single true/false tick
    SELECT = 'select', 'Select'                  # single choice dropdown (uses options)
    MULTI_SELECT = 'multi_select', 'Multi Select'  # multiple choice (uses options)
    DATE = 'date', 'Date'                        # date picker
    TIME = 'time', 'Time'                        # time picker
    FILE = 'file', 'File Upload'                 # file/image upload
    # SIGNATURE = 'signature', 'Signature'         # signature pad (mobile)


class SafetyFormTemplate(models.Model):
    """
    A named form template created by admin.
    e.g. 'Daily Vehicle Check', 'Site Hazard Assessment'
    Each template holds multiple dynamic fields.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive forms will not appear to employees or be selectable for jobs."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

    class Meta:
        verbose_name = 'Safety Form Template'
        verbose_name_plural = 'Safety Form Templates'
        ordering = ['name']


class SafetyFormField(models.Model):
    """
    A single dynamic field belonging to a SafetyFormTemplate.
    - Admin sets field_type to determine what input is rendered.
    - For SELECT / MULTI_SELECT types, options are stored as a
      comma-separated string e.g. "Good,Fair,Poor".
      The serializer exposes them as a clean list.
    - order controls the position (drag-and-drop from frontend).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        SafetyFormTemplate,
        on_delete=models.CASCADE,
        related_name='fields'
    )
    label = models.CharField(
        max_length=200,
        help_text="Display label shown to the employee e.g. 'Vehicle Condition'"
    )
    field_type = models.CharField(
        max_length=20,
        choices=FieldType.choices,
        default=FieldType.TEXT
    )
    # Comma-separated option values for SELECT / MULTI_SELECT
    # e.g. "Good,Fair,Poor" — blank for all other types
    options = models.TextField(
        blank=True,
        help_text="Comma-separated options for select/multi-select fields e.g. Good,Fair,Poor"
    )
    is_required = models.BooleanField(
        default=False,
        help_text="If true, employee must fill this field before submitting."
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order. Lower number appears first."
    )
    helper_text = models.CharField(
        max_length=300,
        blank=True,
        help_text="Optional hint shown below the field in the form."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"[{self.template.name}] {self.label} ({self.field_type})"

    @property
    def options_list(self):
        """Returns options as a clean Python list. Empty list if no options."""
        if not self.options:
            return []
        return [opt.strip() for opt in self.options.split(',') if opt.strip()]

    class Meta:
        verbose_name = 'Safety Form Field'
        verbose_name_plural = 'Safety Form Fields'
        ordering = ['order', 'created_at']
        # Enforce unique ordering per template
        unique_together = [['template', 'order']]
        
        
class SafetyFormSubmission(models.Model):
    """
    One submission per employee per form per job.
    Once submitted, it is locked — no updates allowed.
    Enforced via unique_together and view-level check.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        'jobs.Job',
        on_delete=models.CASCADE,
        related_name='safety_form_submissions'
    )
    template = models.ForeignKey(
        SafetyFormTemplate,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='safety_form_submissions'
    )
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.template.name} — {self.job.job_id} — {self.employee}"

    class Meta:
        verbose_name = 'Safety Form Submission'
        verbose_name_plural = 'Safety Form Submissions'
        # One submission per employee per form per job — locked after submit
        unique_together = [['job', 'template', 'employee']]
        ordering = ['-submitted_at']


class SafetyFormResponse(models.Model):
    """
    One response per field per submission.
    value stores the answer as a string for all field types.
    For FILE fields, value stores the relative media path after saving.
    For CHECKBOX, value is 'true' or 'false'.
    For MULTI_SELECT, value is comma-separated selected options.
    For DATE/TIME, value is ISO string.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission = models.ForeignKey(
        SafetyFormSubmission,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    field = models.ForeignKey(
        SafetyFormField,
        on_delete=models.CASCADE,
        related_name='responses'
    )
    value = models.TextField(blank=True)
    # For FILE type fields — actual file stored here
    file = models.FileField(
        upload_to='safety_forms/uploads/',
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.field.label}: {self.value or '[file]'}"

    class Meta:
        verbose_name = 'Safety Form Response'
        verbose_name_plural = 'Safety Form Responses'
        unique_together = [['submission', 'field']]