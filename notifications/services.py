from firebase_admin import messaging
import logging
from .models import *
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model

User = get_user_model()


logger = logging.getLogger(__name__)


class NotificationService:
    # Unified notification service for FCM (mobile) and WebSocket (web dashboard)
    
    @staticmethod
    def send_notification(
        user,
        notification_type: str,
        title: str,
        body: str,
        data: dict = None,
        priority: str = NotificationPriority.NORMAL,
        send_fcm: bool = True,
        send_websocket: bool = True
    ):
        # Check if the user has notification enabled
        if not user.settings.notification_enabled:
            logger.info(f'Notifications disabled for user {user.email}')
            # return Response({
            #         'warning': 'Notifications disabled for user'
            #     }, status=status.HTTP_406_NOT_ACCEPTABLE
            # )
            return None
        
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            data=data or {},
            priority=priority
        )
        
        # Send via FCM (Mobile)
        if send_fcm and user.settings.notification_enabled:
            fcm_success = NotificationService._send_fcm(
                user=user,
                title=title,
                body=body,
                data=data,
                notification_type=notification_type,
                priority=priority
            )
            notification.sent_via_fcm = True
            notification.fcm_success = fcm_success
            
        # Send via WebSocket
        if send_websocket:
            websocket_success = NotificationService._send_websocket(
                user_id=str(user.id),
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
                priority=priority
            )
            notification.sent_via_websocket = True
            notification.websocket_success = websocket_success
        
        notification.save()
        
        logger.info(
            f'Notification sent to {user.email}: {notification_type} '
            f'(FCM: {notification.fcm_success}, WS: {notification.websocket_success})'
        )
        
        return notification
    
    @staticmethod
    def _send_fcm(user, title, body, data, notification_type, priority):
        # Get all active FCM tokens for this user
        tokens = FCMToken.objects.filter(user=user, is_active=True).values_list('token', flat=True)
        
        if not tokens:
            logger.warning(f'No FCM tokens found for user {user.email}')
            return False
        
        # Prepare FCM message data
        fcm_data = data or {}
        fcm_data.update({
            'notification_type': notification_type,
            'priority': priority,
            'timestamp': timezone.now().isoformat()
        })
        
        # Configure priority for FCM
        android_priority = 'high' if priority in ['high', 'urgent'] else 'normal'
        apns_priority = '10' if priority in ['high', 'urgent'] else '5'
        
        success_count = 0
        failed_tokens = []
        
        for token in tokens:
            try:
                # Create FCM message (works for both iOS and Android!)
                message = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data={k: str(v) for k, v in fcm_data.items()},
                    token=token,
                    # Android-specific config
                    android=messaging.AndroidConfig(
                        priority=android_priority,
                        notification=messaging.AndroidNotification(sound='default', color='#2b63a8')
                    ),
                    # iOS-specific config
                    apns=messaging.APNSConfig(
                        headers={'apns-priority': apns_priority},
                        payload=messaging.APNSPayload(
                            aps=messaging.Aps(sound='default', badge=1)
                        )
                    )
                )
                
                # Send message
                response = messaging.send(message)
                success_count += 1
                logger.info(f'FCM sent successfully: {response}')
                
            except messaging.UnregisteredError:
                # Token is invalid, mark for deletion
                failed_tokens.append(token)
                logger.warning(f'Invalid FCM token: {token}')
                
            except Exception as e:
                logger.error(f'FCM send failed for token {token}: {str(e)}')
                
        # Remove invalid tokens
        if failed_tokens:
            FCMToken.objects.filter(token__in=failed_tokens).update(is_active=False)
        
        return success_count > 0
    
    @staticmethod
    def _send_websocket(user_id, notification_type, title, body, data, priority):
        try:
            channel_layer = get_channel_layer()
            group_name = f'user_{user_id}'
            
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'notification_message',
                    'notification_type': notification_type,
                    'title': title,
                    'body': body,
                    'data': data or {},
                    'priority': priority,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            return True
        
        except Exception as e:
            logger.error(f'WebSocket send failed: {str(e)}')
            return False
        
    @staticmethod
    def send_to_admins(notification_type, title, body, data=None):
        admins = User.objects.filter(is_staff=True, is_active=True)
        
        for admin in admins:
            NotificationService.send_notification(
                user=admin,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
                send_fcm=False,
                send_websocket=True
            )
    

class NotificationTemplates:
    
    @staticmethod
    def welcome(user):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.WELCOME,
            title='Welcome to Autointel Diagnostics App',
            body=f'Hi {user.full_name}, welcome aboard! Get started by adding your first vehicle.',
            priority=NotificationPriority.NORMAL
        )
    
    @staticmethod
    def password_updated(user):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.PASSWORD_UPDATED,
            title='Password Updated Successfully',
            body="Your password has been changed. If this wasn't you, please contact support immediately.",
            priority=NotificationPriority.HIGH
        )
    
    @staticmethod
    def password_changed(user):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.PASSWORD_CHANGED,
            title='Password Changed Successfully',
            body="Your password has been changed. If this wasn't you, please contact support immediately.",
            priority=NotificationPriority.HIGH
        )
    
    
    @staticmethod
    def vehicle_registered(user, vehicle):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.VEHICLE_REGISTERED,
            title='Vehicle Added Successfully',
            body=f'{vehicle.manufacturer} {vehicle.model} has been added to your garage.',
            data={'vehicle_id': str(vehicle.id)},
            priority=NotificationPriority.NORMAL
        )
    
    @staticmethod
    def maintenance_added(user, task):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.MAINTENANCE_ADDED,
            title='Maintenance Task Created',
            body=f"New task: {task.service_type} - Due on {task.next_due_date.strftime('%B %d, %Y')}",
            data={'task_id': str(task.id)},
            priority=NotificationPriority.NORMAL
        )
        
    @staticmethod
    def maintenance_completed(user, task):
        # Notify user when they complete a maintenance task
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.MAINTENANCE_COMPLETED,
            title='Task Completed!',
            body=f'Great job! You completed: {task.service_type}',
            data={'task_id': str(task.id)},
            priority=NotificationPriority.LOW,
            send_fcm=True,  # Send to mobile
            send_websocket=False  # Don't need WebSocket for this
        )
        
    @staticmethod
    def maintenance_due(user, task, days_until_due):
        if days_until_due == 0:
            body = f'{task.service_type} is due today!'
            priority = NotificationPriority.HIGH
        elif days_until_due < 0:
            body = f'{task.service_type} is {abs(days_until_due)} days overdue!'
            priority = NotificationPriority.URGENT
        else:
            body = f'{task.service_type} is due in {days_until_due} days.'
            priority = NotificationPriority.NORMAL
        
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.MAINTENANCE_DUE,
            title='Maintenance Reminder',
            body=body,
            data={
                'task_id': str(task.id),
                'days_until_due': days_until_due
            },
            priority=priority
        )
        
    @staticmethod
    def diagnostic_saved(user, report_id):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.DIAGNOSTIC_SAVED,
            title='Diagnostic Report Saved',
            body='Your vehicle diagnostic report has been saved successfully.',
            data={'report_id': str(report_id)},
            priority=NotificationPriority.NORMAL
        )
    
    @staticmethod
    def subscription_purchased(user, plan_name, expires_at):
        # Notify user of successful subscription purchase
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.SUBSCRIPTION_PURCHASED,
            title='Subscription Activated!',
            body=f'Your {plan_name} subscription is now active until {expires_at.strftime("%B %d, %Y")}.',
            data={
                'plan_name': plan_name,
                'expires_at': expires_at.isoformat()
            },
            priority=NotificationPriority.HIGH
        )

    @staticmethod
    def subscription_expiring(user, days_left):
        # Notify user of expiring subscription
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.SUBSCRIPTION_EXPIRING,
            title='Subscription Expiring Soon',
            body=f'Your premium subscription expires in {days_left} days. Renew now to keep enjoying premium features!',
            data={'days_left': days_left},
            priority=NotificationPriority.HIGH
        )

    @staticmethod
    def subscription_expired(user):
        # Notify user of expired subscription
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.SUBSCRIPTION_EXPIRED,
            title='Subscription Expired',
            body='Your premium subscription has expired. Renew to continue enjoying premium features.',
            priority=NotificationPriority.NORMAL
        )
    
    @staticmethod
    def app_update_available(user, version):
        return NotificationService.send_notification(
            user=user,
            notification_type=NotificationType.APP_UPDATE,
            title='Update Available',
            body=f'Version {version} is available! Update now for new features and improvements.',
            data={'version': version},
            priority=NotificationPriority.LOW
        )
    
    #######################    
    # Admin notifications #
    #######################
    @staticmethod
    def new_user_joined(new_user):
        return NotificationService.send_to_admins(
            notification_type=NotificationType.NEW_USER,
            title='New User Registered',
            body=f'{new_user.full_name} just joined the app!',
            data={'user_id': str(new_user.id)}
        )
    
    @staticmethod
    def milestone_achieved(milestone_type, count):
        return NotificationService.send_to_admins(
            notification_type=NotificationType.MILESTONE_ACHIEVED,
            title=f'Milestone Achieved!',
            body=f"Congratulations! You've reached {count} {milestone_type}!",
            data={
                'milestone_type': milestone_type,
                'count': count
            }
        )
    
    @staticmethod
    def support_request_received(support_ticket):
        return NotificationService.send_to_admins(
            notification_type=NotificationType.SUPPORT_REQUEST,
            title='New Support Request',
            body=f'{support_ticket.user.full_name} submitted a support request: {support_ticket.subject}',
            data={'ticket_id': str(support_ticket.id)}
        )
        
