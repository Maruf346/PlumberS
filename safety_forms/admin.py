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