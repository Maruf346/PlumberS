from django.contrib import admin
from django.utils.html import format_html
from .models import Job, JobAttachment, JobLineItem, JobActivity, JobStatus


class JobAttachmentInline(admin.TabularInline):
    model = JobAttachment
    extra = 0
    fields = ['file', 'file_name', 'uploaded_by', 'uploaded_at']
    readonly_fields = ['file_name', 'uploaded_by', 'uploaded_at']
    can_delete = True


class JobLineItemInline(admin.TabularInline):
    model = JobLineItem
    extra = 1
    fields = ['item', 'quantity', 'unit_price', 'order']


class JobActivityInline(admin.TabularInline):
    model = JobActivity
    extra = 0
    fields = ['activity_type', 'actor', 'description', 'created_at']
    readonly_fields = ['activity_type', 'actor', 'description', 'created_at']
    can_delete = False
    ordering = ['created_at']


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = [
        'job_id', 'job_name', 'status_badge', 'priority',
        'client', 'assigned_to', 'scheduled_datetime', 'created_at',
    ]
    list_filter = ['status', 'priority']
    search_fields = ['job_id', 'job_name', 'client__name', 'assigned_to__email']
    readonly_fields = ['id', 'job_id', 'created_at', 'updated_at']
    filter_horizontal = ['safety_forms', 'assigned_managers']
    ordering = ['-created_at']
    inlines = [JobAttachmentInline, JobLineItemInline, JobActivityInline]

    fieldsets = (
        ('Job Info', {
            'fields': ('id', 'job_id', 'job_name', 'job_details', 'priority', 'status'),
        }),
        ('Scheduling', {
            'fields': ('scheduled_datetime',),
        }),
        ('Assignments', {
            'fields': ('client', 'assigned_to', 'assigned_managers', 'vehicle'),
        }),
        ('Forms', {
            'fields': ('safety_forms',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        color_map = {
            JobStatus.PENDING: '#888888',
            JobStatus.IN_PROGRESS: '#2980B9',
            JobStatus.COMPLETED: '#27AE60',
            JobStatus.OVERDUE: '#E74C3C',
        }
        color = color_map.get(obj.status, '#999')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


@admin.register(JobActivity)
class JobActivityAdmin(admin.ModelAdmin):
    list_display = ['job', 'activity_type', 'actor', 'description', 'created_at']
    list_filter = ['activity_type']
    search_fields = ['job__job_id', 'actor__email', 'description']
    readonly_fields = ['job', 'activity_type', 'actor', 'description', 'created_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False