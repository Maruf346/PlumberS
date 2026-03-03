from django.db import models
from django.contrib.auth import get_user_model
import uuid


User = get_user_model()


class NotificationType(models.TextChoices):
    # User notifications
    WELCOME = 'welcome', 'Welcome'
    PASSWORD_UPDATED = 'pass_updated', 'Password Updated'
    PASSWORD_CHANGED = 'pass_changed', 'Password Changed'
    VEHICLE_REGISTERED = 'vehicle_registered', 'Vehicle Registered'
    MAINTENANCE_ADDED = 'maintenance_added', 'Maintenance Added'
    MAINTENANCE_COMPLETED = 'maintenance_completed', 'Maintenance Completed'  
    MAINTENANCE_DUE = 'maintenance_due', 'Maintenance Due'
    DIAGNOSTIC_SAVED = 'diagnostic_saved', 'Diagnostic Report Saved'
    SUBSCRIPTION_PURCHASED = 'subs_purchased', 'Subscription Purchased'
    SUBSCRIPTION_EXPIRING = 'subs_expiring', 'Subscription Expiring'
    SUBSCRIPTION_EXPIRED = 'subs_expired', 'Subscription Expired'
    APP_UPDATE = 'app_update', 'App Update Available'
    
    # Admin notifications
    NEW_USER = 'new_user', 'New User Joined'
    MILESTONE_ACHIEVED = 'milestone_achieved', 'Milestone Achieved'
    SUPPORT_REQUEST = 'support_request', 'Support Request'

    
class NotificationPriority(models.TextChoices):
    LOW = 'low', 'Low'
    NORMAL = 'normal', 'Normal'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'
    

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=50, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    priority = models.CharField(max_length=20, choices=NotificationPriority.choices, default=NotificationPriority.NORMAL)
    
    # Delivery status
    sent_via_fcm = models.BooleanField(default=False)
    sent_via_websocket = models.BooleanField(default=False)
    fcm_success = models.BooleanField(default=False)
    websocket_success = models.BooleanField(default=False)
    
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
        return f'{self.title} - {self.user.email}'
    
    
class DeviceType(models.TextChoices):
    IOS = 'ios', 'iOS'
    ANDROID = 'android', 'Android'
    
    
class FCMToken(models.Model):
    # To handle multiple devices of a single user
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_tokens')
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=20, choices=DeviceType.choices)
    device_name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'FCM Token'
        verbose_name_plural = 'FCM Tokens'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f'{self.user.email} - {self.device_type}'
