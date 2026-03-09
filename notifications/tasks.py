from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task
def notify_overdue_jobs():
    """
    Runs alongside mark_overdue_jobs beat task.
    Sends notifications for newly overdue jobs.
    """
    from jobs.models import Job, JobStatus
    from notifications.services import NotificationTemplates

    overdue_jobs = Job.objects.filter(
        status=JobStatus.OVERDUE
    ).select_related('assigned_to', 'client')

    for job in overdue_jobs:
        NotificationTemplates.job_overdue(job)

    logger.info(f'Sent overdue notifications for {overdue_jobs.count()} jobs')


@shared_task
def notify_vehicle_service_overdue():
    """
    Notify managers about vehicles that are overdue for service.
    Add to Celery beat — run daily.
    """
    from fleets.models import Vehicle, VehicleStatus
    from notifications.services import NotificationTemplates

    overdue_vehicles = Vehicle.objects.filter(
        status=VehicleStatus.SERVICE_OVERDUE,
        is_active=True
    )

    for vehicle in overdue_vehicles:
        NotificationTemplates.vehicle_service_overdue(vehicle)

    logger.info(f'Sent service overdue notifications for {overdue_vehicles.count()} vehicles')