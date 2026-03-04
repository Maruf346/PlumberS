from django.contrib import admin
from .models import Job, JobAttachment, JobPhoto, JobLineItem, JobTask, JobNote, JobActivity


class JobAttachmentInline(admin.TabularInline):
    model = JobAttachment
    extra = 0
    fields = ['file', 'file_name', 'uploaded_by', 'uploaded_at']
    readonly_fields = ['file_name', 'uploaded_at']


class JobTaskInline(admin.TabularInline):
    model = JobTask
    extra = 0
    fields = ['description', 'is_done', 'order', 'completed_by', 'completed_at']
    readonly_fields = ['completed_by', 'completed_at']


class JobActivityInline(admin.TabularInline):
    model = JobActivity
    extra = 0
    readonly_fields = ['activity_type', 'actor', 'description', 'created_at']
    can_delete = False


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['job_id', 'status', 'priority', 'client', 'assigned_to', 'scheduled_datetime']
    list_filter = ['status', 'priority']
    search_fields = ['job_id', 'insured_name', 'client__name']
    readonly_fields = ['id', 'job_id', 'created_at', 'updated_at']
    inlines = [JobAttachmentInline, JobTaskInline, JobActivityInline]


@admin.register(JobActivity)
class JobActivityAdmin(admin.ModelAdmin):
    list_display = ['job', 'activity_type', 'actor', 'created_at']
    list_filter = ['activity_type']
    readonly_fields = ['job', 'activity_type', 'actor', 'description', 'created_at']