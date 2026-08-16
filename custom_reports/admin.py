from django.contrib import admin

from .models import (
    CustomReportField,
    CustomReportResponse,
    CustomReportSubmission,
    CustomReportTemplate,
)


class CustomReportFieldInline(admin.TabularInline):
    model = CustomReportField
    extra = 1
    fields = ('label', 'field_type', 'options', 'is_required', 'order', 'helper_text')


@admin.register(CustomReportTemplate)
class CustomReportTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'field_count', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    inlines = [CustomReportFieldInline]

    def field_count(self, obj):
        return obj.fields.count()


@admin.register(CustomReportField)
class CustomReportFieldAdmin(admin.ModelAdmin):
    list_display = ('label', 'template', 'field_type', 'is_required', 'order')
    list_filter = ('field_type', 'is_required', 'template')
    search_fields = ('label', 'template__name')


class CustomReportResponseInline(admin.TabularInline):
    model = CustomReportResponse
    extra = 0
    readonly_fields = ('field', 'value', 'file')
    can_delete = False


@admin.register(CustomReportSubmission)
class CustomReportSubmissionAdmin(admin.ModelAdmin):
    list_display = ('template', 'job', 'employee', 'submitted_at')
    list_filter = ('template', 'submitted_at')
    search_fields = ('template__name', 'job__job_id', 'employee__email', 'employee__full_name')
    readonly_fields = ('job', 'template', 'employee', 'submitted_at')
    inlines = [CustomReportResponseInline]
