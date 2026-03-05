from django.contrib import admin
from .models import VehicleInspection, InspectionCheckItem, InspectionCheckPhoto


class InspectionCheckPhotoInline(admin.TabularInline):
    model = InspectionCheckPhoto
    extra = 0
    readonly_fields = ['uploaded_at']


class InspectionCheckItemInline(admin.TabularInline):
    model = InspectionCheckItem
    extra = 0
    readonly_fields = ['created_at', 'updated_at']


@admin.register(VehicleInspection)
class VehicleInspectionAdmin(admin.ModelAdmin):
    list_display = [
        'vehicle', 'inspected_by', 'status',
        'has_open_issue', 'started_at', 'submitted_at'
    ]
    list_filter = ['status', 'has_open_issue']
    search_fields = ['vehicle__name', 'vehicle__plate', 'inspected_by__full_name']
    readonly_fields = ['id', 'started_at', 'submitted_at', 'updated_at']
    inlines = [InspectionCheckItemInline]


@admin.register(InspectionCheckItem)
class InspectionCheckItemAdmin(admin.ModelAdmin):
    list_display = ['inspection', 'category', 'is_ok', 'created_at']
    list_filter = ['category', 'is_ok']
    search_fields = ['inspection__vehicle__name']
    inlines = [InspectionCheckPhotoInline]