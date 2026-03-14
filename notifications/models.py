from django.db import models
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


class NotificationType(models.TextChoices):
    # Auth
    WELCOME = 'welcome', 'Welcome'
    PASSWORD_UPDATED = 'pass_updated', 'Password Updated'
    PASSWORD_CHANGED = 'pass_changed', 'Password Changed'

    # Jobs
    JOB_ASSIGNED = 'job_assigned', 'Job Assigned'
    JOB_UPDATED = 'job_updated', 'Job Updated'
    JOB_STARTED = 'job_started', 'Job Started'
    JOB_COMPLETED = 'job_completed', 'Job Completed'
    JOB_OVERDUE = 'job_overdue', 'Job Overdue'
    JOB_RESCHEDULED = 'job_rescheduled', 'Job Rescheduled'

    # Reports                          ← ADD THIS BLOCK
    REPORT_SUBMITTED = 'report_submitted', 'Report Submitted'

    # Safety forms
    SAFETY_FORM_SUBMITTED = 'safety_form_submitted', 'Safety Form Submitted'

    # Fleet
    VEHICLE_ISSUE_REPORTED = 'vehicle_issue_reported', 'Vehicle Issue Reported'
    VEHICLE_INSPECTION_DUE = 'vehicle_inspection_due', 'Vehicle Inspection Due'
    VEHICLE_SERVICE_OVERDUE = 'vehicle_service_overdue', 'Vehicle Service Overdue'

    # Support
    SUPPORT_REQUEST = 'support_request', 'Support Request'
    ISSUE_REPORT = 'issue_report', 'Issue Report'

    # Admin
    NEW_USER = 'new_user', 'New User Joined'


class NotificationPriority(models.TextChoices):
    LOW = 'low', 'Low'
    NORMAL = 'normal', 'Normal'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['notification_type']),
        ]

    def __str__(self):
        return f'{self.title} — {self.user.email}'