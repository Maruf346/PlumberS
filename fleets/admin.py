from django.contrib import admin
from .models import Vehicle, MaintenanceSchedule


class MaintenanceInline(admin.TabularInline):
    model = MaintenanceSchedule
    extra = 0
    fields = ['scheduled_date', 'description', 'status', 'cost', 'performed_by']
    ordering = ['-scheduled_date']


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ['name', 'plate', 'status', 'next_service_km', 'is_active']
    list_filter = ['status', 'is_active']
    search_fields = ['name', 'plate']
    readonly_fields = ['id', 'status', 'created_at', 'updated_at']
    inlines = [MaintenanceInline]


@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(admin.ModelAdmin):
    list_display = ['vehicle', 'scheduled_date', 'status', 'performed_by', 'cost']
    list_filter = ['status']
    search_fields = ['vehicle__name', 'vehicle__plate', 'performed_by']