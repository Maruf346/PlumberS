from django.contrib import admin
from .models import Note, Task

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'staff', 'due_date', 'estimated_cost', 'created_at']
    list_filter = ['due_date']
    search_fields = ['name', 'staff__full_name']

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'job', 'scheduled_datetime', 'end_time', 'created_at']
    list_filter = ['scheduled_datetime']
    search_fields = ['title', 'job__job_id']
    raw_id_fields = ['job', 'created_by']
