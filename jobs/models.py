from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class JobStatus(models.TextChoices):
    SCHEDULED = 'scheduled', 'Scheduled'
    PENDING = 'pending', 'To be booked'
    IN_PROGRESS = 'in_progress', 'In Progress'
    ON_HOLD = 'on_hold', 'On Hold'
    TO_INVOICE = 'to_invoice', 'To Invoice'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'
    EMERGENCY_MAKE_SAFE = 'emergency_make_safe', 'Emergency Make Safe'
    OVERDUE = 'overdue', 'Overdue'


class JobPriority(models.TextChoices):
    LOW = 'low', 'Low'
    MEDIUM = 'medium', 'Medium'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'


class ActivityType(models.TextChoices):
    JOB_CREATED = 'job_created', 'Job Created'
    JOB_ASSIGNED = 'job_assigned', 'Job Assigned'
    JOB_STARTED = 'job_started', 'Job Started'
    TECHNICIAN_EN_ROUTE = 'technician_en_route', 'Technician En Route'
    ARRIVED_AT_SITE = 'arrived_at_site', 'Arrived at Site'
    SAFETY_FORM_SUBMITTED = 'safety_form_submitted', 'Safety Form Submitted'
    REPORT_SUBMITTED = 'report_submitted', 'Report Submitted'       # ← NEW
    # TASK_COMPLETED = 'task_completed', 'Task Completed'           # commented — tasks feature off
    NOTE_ADDED = 'note_added', 'Note Added'
    FILE_UPLOADED = 'file_uploaded', 'File Uploaded'
    STATUS_CHANGED = 'status_changed', 'Status Changed'
    JOB_COMPLETED = 'job_completed', 'Job Completed'
    JOB_RESCHEDULED = 'job_rescheduled', 'Job Rescheduled'


def job_attachment_path(instance, filename):
    return f'jobs/{instance.job.job_id}/attachments/{filename}'


def job_photo_path(instance, filename):           # commented — job photos now live in reports
    return f'jobs/{instance.job.job_id}/photos/{filename}'


class Job(models.Model):
    """
    Core job model.
    Status logic:
    - PENDING:     No assigned_to, or created but not started.
    - IN_PROGRESS: Assigned employee has started the job.
    - COMPLETED:   Assigned employee marked it complete.
    - OVERDUE:     scheduled_datetime has passed and job is not completed.
                   Checked via Celery beat task or on retrieval.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_id = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        help_text="Auto-generated human-readable ID e.g. JB-1023"
    )

    # Status & priority
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.PENDING
    )
    pre_overdue_status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        null=True,
        blank=True,
        editable=False,
        help_text="Stores the status before the job became overdue, used to restore on reschedule"
    )
    priority = models.CharField(
        max_length=10,
        choices=JobPriority.choices,
        default=JobPriority.MEDIUM
    )

    # Core details
    job_name = models.CharField(max_length=200, blank=True)
    job_details = models.TextField(blank=True)
    
    # Insured details — filled manually by admin at job creation
    insured_name = models.CharField(max_length=150, blank=True)
    insured_phone = models.CharField(max_length=30, blank=True)
    insured_email = models.EmailField(blank=True)
    insured_address = models.CharField(max_length=500, blank=True)
    site_access_info = models.TextField(
        blank=True,
        help_text="Gate codes, access instructions, entry notes etc."
    )

    # Scheduling
    scheduled_datetime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time the job is scheduled for"
    )

    # Relations
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_jobs',
        limit_choices_to={'is_staff': False, 'is_superuser': False},
        help_text="Single employee (plumber) assigned to this job"
    )
    assigned_managers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='managed_jobs',
        limit_choices_to={'is_staff': True, 'is_superuser': False},
        help_text="One or more managers overseeing this job"
    )
    vehicle = models.ForeignKey(
        'fleets.Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='jobs',
        help_text="Vehicle assigned to this job"
    )

    # Safety forms — multiple templates can be attached per job
    safety_forms = models.ManyToManyField(
        'safety_forms.SafetyFormTemplate',
        blank=True,
        related_name='jobs',
        help_text="Safety form templates required for this job"
    )

    # Report types — managed via reports.JobReport (FK to this model)
    # report_template_ids = models.JSONField(   # REMOVED — replaced by reports.JobReport
    #     default=list,
    #     blank=True,
    #     help_text="List of report template IDs attached to this job"
    # )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.job_id} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.job_id:
            self.job_id = self._generate_job_id()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_job_id():
        from django.db.models import Max

        rows = Job.objects.filter(job_id__startswith='JB-').values_list('job_id', flat=True)

        max_num = 1000  # starting point
        for job_id in rows:
            try:
                num = int(job_id.split('-')[1])
                if num > max_num:
                    max_num = num
            except (IndexError, ValueError):
                continue

        # If any rows exist, increment; otherwise start at 1001
        if rows.exists():
            return f"JB-{max_num + 1}"
        return "JB-1001"

    def check_overdue(self):
        if (
            self.scheduled_datetime and
            timezone.now() > self.scheduled_datetime and
            self.status not in [JobStatus.COMPLETED]
        ):
            self.status = JobStatus.OVERDUE
            Job.objects.filter(pk=self.pk).update(status=JobStatus.OVERDUE)

    @property
    def is_overdue(self):
        if not self.scheduled_datetime:
            return False
        return (
            timezone.now() > self.scheduled_datetime and
            self.status != JobStatus.COMPLETED
        )

    @property
    def has_fleet_issue(self):
        if self.vehicle:
            from fleets.models import VehicleStatus
            return self.vehicle.status != VehicleStatus.HEALTHY
        return False

    class Meta:
        verbose_name = 'Job'
        verbose_name_plural = 'Jobs'
        ordering = ['-created_at']


class JobAttachment(models.Model):
    """Files attached to a job by admin at creation or during the job."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=job_attachment_path)
    file_name = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.file_name and self.file:
            self.file_name = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.job.job_id} — {self.file_name}"


# ── JobPhoto — commented out; photos now submitted via reports app ──────────
# class JobPhoto(models.Model):
#     """Photos uploaded during job execution, with captions."""
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='photos')
#     image = models.ImageField(upload_to=job_photo_path)
#     caption = models.CharField(max_length=300, blank=True)
#     uploaded_by = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.SET_NULL,
#         null=True
#     )
#     uploaded_at = models.DateTimeField(auto_now_add=True)
#
#     def __str__(self):
#         return f"{self.job.job_id} — photo"


class JobLineItem(models.Model):
    """
    Scope line items for a job.
    Each row: item description, qty, unit price, auto-computed subtotal.
    Grand total computed across all rows in serializer.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='line_items')
    item = models.CharField(max_length=300)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    order = models.PositiveIntegerField(default=0)

    @property
    def total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.job.job_id} — {self.item}"

    class Meta:
        ordering = ['order']


# ── JobTask — commented out; checklist feature deferred ─────────────────────
# class JobTask(models.Model):
#     """Checklist items for a job. Employee marks each as done."""
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='tasks')
#     description = models.CharField(max_length=300)
#     is_done = models.BooleanField(default=False)
#     completed_by = models.ForeignKey(
#         settings.AUTH_USER_MODEL,
#         on_delete=models.SET_NULL,
#         null=True,
#         blank=True,
#         related_name='completed_tasks'
#     )
#     completed_at = models.DateTimeField(null=True, blank=True)
#     order = models.PositiveIntegerField(default=0)
#
#     def mark_done(self, user):
#         self.is_done = True
#         self.completed_by = user
#         self.completed_at = timezone.now()
#         self.save()
#
#     def __str__(self):
#         return f"{self.job.job_id} — {self.description}"
#
#     class Meta:
#         ordering = ['order']


# ── Add this back to jobs/models.py ──────────────────────────────────────────
# Place it after JobLineItem, before JobActivity


class JobNote(models.Model):
    """
    Per-job ticket-style communication between assigned employee and admin/manager.
    No WebSocket — simple POST to send, GET to list. Ordered oldest-first so it
    renders like a chat thread.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='job_notes'
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.job.job_id} — {self.sender} at {self.created_at}"

    class Meta:
        ordering = ['created_at']   # oldest first → natural chat order


class JobActivity(models.Model):
    """
    Immutable audit log for a job.
    One entry per significant event — used for the activity timeline.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ActivityType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='job_activities'
    )
    description = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.job.job_id} — {self.activity_type}"

    class Meta:
        ordering = ['created_at']