from celery import shared_task
from django.utils import timezone
from datetime import timedelta
# from maintenance.models import ManualMaintenanceTask
from notifications.services import NotificationTemplates
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


# @shared_task
# def send_maintenance_due_reminders():
#     # Send daily reminders for maintenance tasks due soon
#     # Run this daily at 9 AM using Celery Beat
    
#     today = timezone.now().date()
    
#     # Get tasks due in 7 days, 3 days, 1 day, and overdue
#     reminder_days = [7, 3, 1, 0, -1]  # 0 = today, -1 = yesterday (overdue)
    
#     for days in reminder_days:
#         due_date = today + timedelta(days=days)
        
#         tasks = ManualMaintenanceTask.objects.filter(next_due_date=due_date, is_completed=False).select_related('user')
        
#         for task in tasks:
#             days_until_due = (task.next_due_date - today).days
#             NotificationTemplates.maintenance_due(user=task.user, task=task, days_until_due=days_until_due)
            
#         logger.info(f'Sent {tasks.count()} maintenance reminders for due date {due_date}')
        
        
# @shared_task
# def send_subscription_expiry_reminders():
#     # Send reminders for expiring subscriptions
#     # Run this daily
    
#     today = timezone.now().date()
    
#     # Remind at 7 days, 3 days, and 1 day before expiry
#     for days in [7, 3, 1]:
#         expiry_date = today + timedelta(days=days)
        
#         users = User.objects.filter(
#             is_premium=True,
#             # Assuming you have subscription_expires_at field
#             # subscription_expires_at__date=expiry_date
#         )
        
#         for user in users:
#             NotificationTemplates.subscription_expiring(user, days)
        
#         logger.info(f'Sent subscription expiry reminders to {users.count()} users')


# @shared_task
# def check_milestones():
    # Check and notify admins about milestones
    # Run this hourly or when events happen

    # from user.models import User
    
    # total_users = User.objects.count()
    
    # # Define milestones
    # milestones = [100, 500, 1000, 5000, 10000, 50000, 100000]
    
    # for milestone in milestones:
    #     if total_users == milestone:
    #         NotificationTemplates.milestone_achieved('users', milestone)
    #         logger.info(f"Milestone achieved: {milestone} users")
    #         break