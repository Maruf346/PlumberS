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
    # 'send-maintenance-reminders-daily': {
    #     'task': 'notifications.tasks.send_maintenance_due_reminders',
    #     'schedule': crontab(hour=9, minute=0),  # Every day at 9 AM
    # },
    # 'send-subscription-reminders-daily': {
    #     'task': 'notifications.tasks.send_subscription_expiry_reminders',
    #     'schedule': crontab(hour=10, minute=0),  # Every day at 10 AM
    # },
    # 'check-milestones-hourly': {
    #     'task': 'notifications.tasks.check_milestones',
    #     'schedule': crontab(minute=0),  # Every hour
    # },
    
    #  'check-expired-subscriptions-daily': {
    #     'task': 'subscriptions.tasks.check_expired_subscriptions',
    #     'schedule': crontab(hour=0, minute=30),  # Every day at 12:30 AM
    # },
    # 'send-subscription-expiry-reminders-daily': {
    #     'task': 'subscriptions.tasks.send_subscription_expiry_reminders',
    #     'schedule': crontab(hour=9, minute=0),  # Every day at 9 AM
    # },
}
