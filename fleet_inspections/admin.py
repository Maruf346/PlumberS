from django.contrib import admin
from .models import VehicleInspection, InspectionCheckItem, InspectionCheckPhoto


class InspectionCheckPhotoInline(admin.TabularInline):
    model = InspectionCheckPhoto
    extra = 0
    readonly_fields = ['uploaded_at']


class InspectionCheckItemInline(admin.TabularInline):
    model = InspectionCheckItem
    extra = 0
    readonly_fields = ['created_at']
    inlines = []


@admin.register(VehicleInspection)
class VehicleInspectionAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'inspected_by', 'has_open_issue', 'inspected_at']
    list_filter = ['has_open_issue']
    search_fields = ['vehicle__name', 'vehicle__plate', 'inspected_by__full_name']
    readonly_fields = ['id', 'has_open_issue', 'inspected_at', 'updated_at']
    inlines = [InspectionCheckItemInline]


@admin.register(InspectionCheckItem)
class InspectionCheckItemAdmin(admin.ModelAdmin):
    list_display = ['inspection', 'category', 'is_ok', 'created_at']
    list_filter = ['category', 'is_ok']
    inlines = [InspectionCheckPhotoInline]
