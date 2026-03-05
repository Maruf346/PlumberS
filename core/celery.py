import os
from celery import Celery
from celery.schedules import crontab


# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')   # Creates a celery app named 'core'

# Load task modules from all registered Django apps
app.config_from_object('django.conf:settings', namespace='CELERY')  # Settings vars that starts with CELERY_...

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# @app.task → registers this as a Celery task.
# ignore_result: Celery will not store the task result
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
    

# Celery Beat Schedule
app.conf.beat_schedule = {
    'mark-overdue-jobs': {
        'task': 'jobs.tasks.mark_overdue_jobs',
        'schedule': crontab(minute='*/30'),
    },
}
