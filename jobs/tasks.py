from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def mark_overdue_jobs():
    """
    Runs every 30 minutes via Celery beat.
    Marks any PENDING or IN_PROGRESS job past its scheduled_datetime as OVERDUE.
    COMPLETED jobs are never marked overdue.
    """
    from .models import Job, JobStatus

    overdue_candidates = Job.objects.filter(
        scheduled_datetime__lt=timezone.now()
    ).exclude(
        status__in=[JobStatus.COMPLETED]
    )

    count = overdue_candidates.count()
    if count:
        overdue_candidates.update(status=JobStatus.OVERDUE)
        logger.info(f'Marked {count} job(s) as overdue.')
    else:
        logger.debug('No jobs to mark overdue.')

    return f'{count} jobs marked overdue'