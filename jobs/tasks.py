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

    now = timezone.now()

    # ── Step 1: Mark newly overdue ────────────────────────────────────────────
    newly_overdue = Job.objects.filter(
        scheduled_datetime__lt=now
    ).exclude(
        status__in=[JobStatus.COMPLETED, JobStatus.OVERDUE]
    )

    overdue_count = 0
    for job in newly_overdue:
        # Remember what status the job was in before going overdue
        job.pre_overdue_status = job.status
        job.status = JobStatus.OVERDUE
        job.save(update_fields=['status', 'pre_overdue_status'])
        overdue_count += 1

    if overdue_count:
        logger.info(f'Marked {overdue_count} job(s) as overdue.')

    # ── Step 2: Restore rescheduled jobs ──────────────────────────────────────
    rescheduled = Job.objects.filter(
        status=JobStatus.OVERDUE,
        scheduled_datetime__gt=now
    )

    rescheduled_count = 0
    for job in rescheduled:
        # Restore to whatever it was before — PENDING or IN_PROGRESS
        restore_to = job.pre_overdue_status or JobStatus.PENDING
        job.status = restore_to
        job.pre_overdue_status = None   # clear it
        job.save(update_fields=['status', 'pre_overdue_status'])
        rescheduled_count += 1

    if rescheduled_count:
        logger.info(f'Restored {rescheduled_count} job(s) from OVERDUE.')

    if not overdue_count and not rescheduled_count:
        logger.debug('No overdue changes.')

    return f'{overdue_count} marked overdue, {rescheduled_count} restored'