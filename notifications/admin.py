from django.contrib import admin
from django.utils.html import format_html
from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'user_email',
        'notification_type',
        'priority_badge',
        'is_read',
        'created_at',
    ]

    list_filter = [
        'notification_type',
        'priority',
        'is_read',
        'created_at',
    ]

    search_fields = [
        'title',
        'body',
        'user__email',
        'user__full_name',
    ]

    readonly_fields = [
        'id',
        'created_at',
        'read_at',
    ]

    fieldsets = (
        ('Notification Details', {
            'fields': ('user', 'notification_type', 'title', 'body', 'priority')
        }),
        ('Additional Data', {
            'fields': ('data',),
            'classes': ('collapse',)
        }),
        ('User Interaction', {
            'fields': ('is_read', 'read_at')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at'),
            'classes': ('collapse',)
        }),
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
            'urgent': '#dc3545',
        }
        color = colors.get(obj.priority, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'