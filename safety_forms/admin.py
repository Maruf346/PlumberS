from django.contrib import admin
from .models import SafetyFormTemplate, SafetyFormField


class SafetyFormFieldInline(admin.TabularInline):
    model = SafetyFormField
    extra = 0
    fields = ['label', 'field_type', 'options', 'is_required', 'order', 'helper_text']
    ordering = ['order']


@admin.register(SafetyFormTemplate)
class SafetyFormTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name']
    inlines = [SafetyFormFieldInline]
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(SafetyFormField)
class SafetyFormFieldAdmin(admin.ModelAdmin):
    list_display = ['label', 'template', 'field_type', 'is_required', 'order']
    list_filter = ['field_type', 'is_required', 'template']
    search_fields = ['label', 'template__name']
    ordering = ['template', 'order']
    

from .models import SafetyFormSubmission, SafetyFormResponse

class SafetyFormResponseInline(admin.TabularInline):
    model = SafetyFormResponse
    extra = 0
    readonly_fields = ['field', 'value', 'file']
    can_delete = False

@admin.register(SafetyFormSubmission)
class SafetyFormSubmissionAdmin(admin.ModelAdmin):
    list_display = ['template', 'job', 'employee', 'submitted_at']
    list_filter = ['template']
    search_fields = ['job__job_id', 'employee__full_name', 'template__name']
    readonly_fields = ['id', 'job', 'template', 'employee', 'submitted_at']
    inlines = [SafetyFormResponseInline]