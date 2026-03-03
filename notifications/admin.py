from django.contrib import admin
from django.utils.html import format_html
from notifications.models import Notification, FCMToken


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'user_email',
        'notification_type',
        'priority_badge',
        'delivery_status',
        'is_read',
        'created_at'
    ]
    
    list_filter = [
        'notification_type',
        'priority',
        'is_read',
        'sent_via_fcm',
        'sent_via_websocket',
        'created_at'
    ]
    
    search_fields = [
        'title',
        'body',
        'user__email',
        'user__full_name'
    ]
    
    readonly_fields = [
        'id',
        'created_at',
        'read_at',
        'sent_via_fcm',
        'sent_via_websocket',
        'fcm_success',
        'websocket_success'
    ]
    
    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'notification_type', 'title', 'body', 'priority')
        }),
        ('Additional Data', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
        ('Delivery Status', {
            'fields': (
                'sent_via_fcm',
                'fcm_success',
                'sent_via_websocket',
                'websocket_success'
            )
        }),
        ('User Interaction', {
            'fields': ('is_read', 'read_at')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        })
    )
    
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
    
    def priority_badge(self, obj):
        colors = {
            'low': '#6c757d',
            'normal': '#007bff',
            'high': '#fd7e14',
            'urgent': '#dc3545'
        }
        color = colors.get(obj.priority, '#6c757d')
        
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    
    def delivery_status(self, obj):
        fcm_icon = '✅' if obj.fcm_success else ('❌' if obj.sent_via_fcm else '➖')
        ws_icon = '✅' if obj.websocket_success else ('❌' if obj.sent_via_websocket else '➖')
        
        return format_html(
            'FCM: {} | WS: {}',
            fcm_icon,
            ws_icon
        )
    delivery_status.short_description = 'Delivery'


@admin.register(FCMToken)
class FCMTokenAdmin(admin.ModelAdmin):
    list_display = [
        'user_email',
        'device_type',
        'device_name',
        'is_active',
        'created_at',
        'updated_at'
    ]
    
    list_filter = [
        'device_type',
        'is_active',
        'created_at'
    ]
    
    search_fields = [
        'user__email',
        'user__full_name',
        'device_name',
        'token'
    ]
    
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('User & Device', {
            'fields': ('user', 'device_type', 'device_name')
        }),
        ('Token', {
            'fields': ('token', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'