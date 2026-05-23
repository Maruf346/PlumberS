from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task
def mark_overdue_jobs():
    """
    Runs every 30 minutes via Celery beat.
    A job is overdue when its earliest scheduled Note is in the past and
    the job status is still active (not COMPLETED or CANCELLED).
    COMPLETED/CANCELLED jobs are never marked overdue.
    """
    from .models import Job, JobStatus
    from notes.models import Note

    now = timezone.now()
    skip_statuses = [JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.OVERDUE]

    # ── Step 1: Mark newly overdue ───────────────────────────────────────────
    # Jobs whose earliest note is in the past and aren't already resolved
    overdue_job_ids = Note.objects.filter(
        job__isnull=False,
        scheduled_datetime__lt=now,
    ).exclude(
        job__status__in=skip_statuses
    ).values_list('job_id', flat=True).distinct()

    newly_overdue = Job.objects.filter(id__in=overdue_job_ids)
    overdue_count = 0
    for job in newly_overdue:
        job.pre_overdue_status = job.status
        job.status = JobStatus.OVERDUE
        job.save(update_fields=['status', 'pre_overdue_status'])
        overdue_count += 1

    if overdue_count:
        logger.info(f'Marked {overdue_count} job(s) as overdue.')

    # ── Step 2: Restore jobs whose notes are all rescheduled to future ───────
    # An OVERDUE job should be restored if all its notes are now in the future
    overdue_jobs = Job.objects.filter(status=JobStatus.OVERDUE)
    rescheduled_count = 0
    for job in overdue_jobs:
        has_past_note = Note.objects.filter(
            job=job,
            scheduled_datetime__lt=now,
        ).exists()
        if not has_past_note:
            restore_to = job.pre_overdue_status or JobStatus.PENDING
            job.status = restore_to
            job.pre_overdue_status = None
            job.save(update_fields=['status', 'pre_overdue_status'])
            rescheduled_count += 1

    if rescheduled_count:
        logger.info(f'Restored {rescheduled_count} job(s) from OVERDUE.')

    if not overdue_count and not rescheduled_count:
        logger.debug('No overdue changes.')

    return f'{overdue_count} marked overdue, {rescheduled_count} restored'