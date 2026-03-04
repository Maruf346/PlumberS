from django.db import models
import uuid


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
    SIGNATURE = 'signature', 'Signature'         # signature pad (mobile)


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