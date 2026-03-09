import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Notification, NotificationType, NotificationPriority

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:
    """
    Web-only notification service.
    Saves to DB and pushes via WebSocket (Django Channels).
    No FCM / mobile push notifications.
    """

    @staticmethod
    def send_notification(
        user,
        notification_type: str,
        title: str,
        body: str,
        data: dict = None,
        priority: str = NotificationPriority.NORMAL,
    ):
        # Save to DB
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            priority=priority
        )

        # Push via WebSocket
        ws_success = NotificationService._send_websocket(
            user_id=str(user.id),
            notification_id=str(notification.id),
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            priority=priority,
            created_at=notification.created_at.isoformat(),
        )

        if ws_success:
            logger.info(f'Notification sent via WebSocket to {user.email}: {notification_type}')
        else:
            logger.warning(f'WebSocket delivery failed for {user.email}: {notification_type}')

        return notification

    @staticmethod
    def _send_websocket(
        user_id, notification_id, notification_type,
        title, body, data, priority, created_at
    ):
        try:
            channel_layer = get_channel_layer()
            group_name = f'user_{user_id}'

            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_message',
                    'notification_id': notification_id,
                    'notification_type': notification_type,
                    'title': title,
                    'body': body,
                    'data': data,
                    'priority': priority,
                    'created_at': created_at,
                }
            )
            return True

        except Exception as e:
            logger.error(f'WebSocket send failed for user {user_id}: {str(e)}')
            return False

    @staticmethod
    def send_to_admins(notification_type, title, body, data=None):
        """Send notification to all active admins and managers."""
        staff = User.objects.filter(is_staff=True, is_active=True)
        for user in staff:
            NotificationService.send_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
            )

    @staticmethod
    def send_to_managers(notification_type, title, body, data=None):
        """Send notification to managers only (not superusers)."""
        managers = User.objects.filter(
            is_staff=True,
            is_superuser=False,
            is_active=True
        )
        for user in managers:
            NotificationService.send_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
            )


class NotificationTemplates:
    """
    Ready-made notification templates for all events in the system.
    Call these from views, signals, or Celery tasks.
    """

    # ==================== AUTH ====================

    @staticmethod
    def welcome(user):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.WELCOME,
            title='Welcome to Adelaide Plumbing & Gasfitting',
            body=f'Hi {user.full_name or user.email}, your account is ready. Complete your profile to get started.',
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def password_updated(user):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.PASSWORD_UPDATED,
            title='Password Reset Successfully',
            body="Your password was reset. If this wasn't you, contact your administrator immediately.",
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def password_changed(user):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.PASSWORD_CHANGED,
            title='Password Changed',
            body="Your password was changed successfully. If this wasn't you, contact your administrator.",
            priority=NotificationPriority.HIGH,
        )

    # ==================== JOBS ====================

    @staticmethod
    def job_assigned(user, job):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.JOB_ASSIGNED,
            title='New Job Assigned',
            body=f'You have been assigned to job {job.job_id}: {job.job_name}.',
            data={'job_id': str(job.id), 'job_ref': job.job_id},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def job_updated(user, job):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.JOB_UPDATED,
            title='Job Updated',
            body=f'Job {job.job_id} ({job.job_name}) has been updated.',
            data={'job_id': str(job.id), 'job_ref': job.job_id},
            priority=NotificationPriority.NORMAL,
        )

    @staticmethod
    def job_started(job):
        """Notify managers when employee starts a job."""
        NotificationService.send_to_admins(
            notification_type=NotificationType.JOB_STARTED,
            title='Job Started',
            body=f'{job.assigned_to.full_name} started job {job.job_id}: {job.job_name}.',
            data={'job_id': str(job.id), 'job_ref': job.job_id},
        )

    @staticmethod
    def job_completed(job):
        """Notify managers when employee completes a job."""
        NotificationService.send_to_admins(
            notification_type=NotificationType.JOB_COMPLETED,
            title='Job Completed',
            body=f'{job.assigned_to.full_name} completed job {job.job_id}: {job.job_name}.',
            data={'job_id': str(job.id), 'job_ref': job.job_id},
        )

    @staticmethod
    def job_overdue(job):
        """Notify assigned employee and managers when a job goes overdue."""
        # Notify employee
        if job.assigned_to:
            NotificationService.send_notification(
                user=job.assigned_to,
                notification_type=NotificationType.JOB_OVERDUE,
                title='Job Overdue',
                body=f'Job {job.job_id}: {job.job_name} is now overdue.',
                data={'job_id': str(job.id), 'job_ref': job.job_id},
                priority=NotificationPriority.URGENT,
            )
        # Notify managers
        NotificationService.send_to_admins(
            notification_type=NotificationType.JOB_OVERDUE,
            title='Job Overdue',
            body=f'Job {job.job_id}: {job.job_name} is overdue.',
            data={'job_id': str(job.id), 'job_ref': job.job_id},
        )

    @staticmethod
    def job_rescheduled(user, job):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.JOB_RESCHEDULED,
            title='Job Rescheduled',
            body=f'Job {job.job_id} has been rescheduled to {job.scheduled_datetime.strftime("%d %b %Y, %I:%M %p") if job.scheduled_datetime else "TBD"}.',
            data={'job_id': str(job.id), 'job_ref': job.job_id},
            priority=NotificationPriority.NORMAL,
        )

    # ==================== SAFETY FORMS ====================

    @staticmethod
    def safety_form_submitted(job, template, employee):
        """Notify managers when an employee submits a safety form."""
        NotificationService.send_to_admins(
            notification_type=NotificationType.SAFETY_FORM_SUBMITTED,
            title='Safety Form Submitted',
            body=f'{employee.full_name} submitted "{template.name}" for job {job.job_id}.',
            data={
                'job_id': str(job.id),
                'job_ref': job.job_id,
                'template_id': str(template.id),
                'employee_id': str(employee.id),
            },
        )

    # ==================== FLEET ====================

    @staticmethod
    def vehicle_issue_reported(vehicle, inspection):
        """Notify managers when a vehicle inspection reports an issue."""
        NotificationService.send_to_admins(
            notification_type=NotificationType.VEHICLE_ISSUE_REPORTED,
            title='Vehicle Issue Reported',
            body=f'An issue was reported for vehicle {vehicle.name} ({vehicle.plate}) during inspection.',
            data={
                'vehicle_id': str(vehicle.id),
                'inspection_id': str(inspection.id),
            },
        )

    @staticmethod
    def vehicle_inspection_due(user, vehicle):
        NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.VEHICLE_INSPECTION_DUE,
            title='Vehicle Inspection Due',
            body=f'Vehicle {vehicle.name} ({vehicle.plate}) is due for inspection.',
            data={'vehicle_id': str(vehicle.id)},
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def vehicle_service_overdue(vehicle):
        """Notify all managers when a vehicle is overdue for service."""
        NotificationService.send_to_admins(
            notification_type=NotificationType.VEHICLE_SERVICE_OVERDUE,
            title='Vehicle Service Overdue',
            body=f'Vehicle {vehicle.name} ({vehicle.plate}) is overdue for service.',
            data={'vehicle_id': str(vehicle.id)},
        )

    # ==================== SUPPORT ====================

    @staticmethod
    def support_feedback_received(feedback):
        NotificationService.send_to_admins(
            notification_type=NotificationType.SUPPORT_REQUEST,
            title='New Feedback Received',
            body=f'{feedback.first_name} {feedback.last_name} submitted feedback.',
            data={'feedback_id': str(feedback.id)},
        )

    @staticmethod
    def issue_report_received(report):
        NotificationService.send_to_admins(
            notification_type=NotificationType.ISSUE_REPORT,
            title='New Issue Report',
            body=f'{report.user.full_name} reported an issue: {report.title}',
            data={'report_id': str(report.id)},
        )

    # ==================== ADMIN ====================

    @staticmethod
    def new_user_joined(new_user):
        NotificationService.send_to_admins(
            notification_type=NotificationType.NEW_USER,
            title='New Employee Registered',
            body=f'{new_user.full_name or new_user.email} just registered.',
            data={'user_id': str(new_user.id)},
        )