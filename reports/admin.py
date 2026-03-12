from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
from django.utils.html import format_html
from .models import (
    JobReport, ReportPhoto,
    RoofReportSubmission, ApplianceReportSubmission,
    DrainInspectionSubmission, LeakInspectionSubmission,
    SprayTestSubmission,
)


# ==================== INLINES ====================

class ReportPhotoInline(GenericTabularInline):
    model = ReportPhoto
    extra = 0
    readonly_fields = ['photo_preview', 'photo_type', 'image', 'uploaded_at']
    fields = ['photo_type', 'image', 'photo_preview', 'uploaded_at']
    can_delete = False

    def photo_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px; border-radius:4px;" />',
                obj.image.url
            )
        return '—'
    photo_preview.short_description = 'Preview'


# ==================== JOB REPORT ====================

@admin.register(JobReport)
class JobReportAdmin(admin.ModelAdmin):
    list_display = [
        'job_link', 'report_type_badge', 'is_submitted',
        'submitted_by', 'submitted_at', 'created_at',
    ]
    list_filter = ['report_type', 'is_submitted']
    search_fields = ['job__job_id', 'job__job_name', 'submitted_by__email']
    readonly_fields = [
        'id', 'job', 'report_type', 'assigned_by',
        'is_submitted', 'submitted_by', 'submitted_at', 'created_at',
    ]
    ordering = ['-created_at']

    fieldsets = (
        ('Report Info', {
            'fields': ('id', 'job', 'report_type', 'assigned_by'),
        }),
        ('Submission Status', {
            'fields': ('is_submitted', 'submitted_by', 'submitted_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def job_link(self, obj):
        return format_html(
            '<a href="/admin/jobs/job/{}/change/">{}</a>',
            obj.job.id,
            obj.job.job_id
        )
    job_link.short_description = 'Job'
    job_link.admin_order_field = 'job__job_id'

    def report_type_badge(self, obj):
        color_map = {
            'roof': '#E67E22',
            'appliance': '#2980B9',
            'drain_inspection': '#27AE60',
            'leak_inspection': '#8E44AD',
            'spray_test': '#F54900',
        }
        color = color_map.get(obj.report_type, '#999')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color,
            obj.get_report_type_display()
        )
    report_type_badge.short_description = 'Report Type'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== ROOF REPORT ====================

@admin.register(RoofReportSubmission)
class RoofReportSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'job_id', 'submitted_by', 'attendance_datetime',
        'type_of_dwelling', 'leak_fixed', 'created_at',
    ]
    list_filter = ['type_of_dwelling', 'type_of_roof', 'leak_present', 'leak_fixed']
    search_fields = ['job_report__job__job_id', 'submitted_by__email']
    readonly_fields = ['id', 'job_report', 'submitted_by', 'snapshot', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [ReportPhotoInline]

    fieldsets = (
        ('Job Reference', {
            'fields': ('id', 'job_report', 'submitted_by', 'attendance_datetime'),
        }),
        ('Property', {
            'fields': ('type_of_dwelling', 'type_of_roof', 'pitch_of_roof'),
        }),
        ('Discussion & Damages', {
            'fields': ('discussion_with_insured', 'resulting_damages'),
        }),
        ('Leak Assessment', {
            'fields': (
                'leak_present', 'cause_of_leak_found',
                'leak_fixed', 'leak_fixed_by_insured',
            ),
        }),
        ('Works & Conclusion', {
            'fields': ('works_required', 'conclusion'),
        }),
        ('Snapshot (read-only)', {
            'fields': ('snapshot',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def job_id(self, obj):
        return obj.job_report.job.job_id
    job_id.short_description = 'Job ID'
    job_id.admin_order_field = 'job_report__job__job_id'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== APPLIANCE REPORT ====================

@admin.register(ApplianceReportSubmission)
class ApplianceReportSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'job_id', 'submitted_by', 'attendance_datetime',
        'appliance_brand', 'model_no', 'approx_age', 'created_at',
    ]
    search_fields = [
        'job_report__job__job_id', 'submitted_by__email',
        'appliance_brand', 'model_no',
    ]
    readonly_fields = ['id', 'job_report', 'submitted_by', 'snapshot', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [ReportPhotoInline]

    fieldsets = (
        ('Job Reference', {
            'fields': ('id', 'job_report', 'submitted_by', 'attendance_datetime'),
        }),
        ('Appliance Details', {
            'fields': ('appliance_brand', 'model_no', 'approx_age'),
        }),
        ('Discussion & Conclusion', {
            'fields': ('discussion_with_insured', 'conclusion'),
        }),
        ('Snapshot (read-only)', {
            'fields': ('snapshot',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def job_id(self, obj):
        return obj.job_report.job.job_id
    job_id.short_description = 'Job ID'
    job_id.admin_order_field = 'job_report__job__job_id'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== DRAIN INSPECTION ====================

@admin.register(DrainInspectionSubmission)
class DrainInspectionSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'job_id', 'submitted_by', 'attendance_datetime',
        'property_construction', 'area_of_inspection',
        'pipe_construction', 'created_at',
    ]
    list_filter = ['property_construction', 'area_of_inspection', 'pipe_construction']
    search_fields = ['job_report__job__job_id', 'submitted_by__email']
    readonly_fields = ['id', 'job_report', 'submitted_by', 'snapshot', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [ReportPhotoInline]

    fieldsets = (
        ('Job Reference', {
            'fields': ('id', 'job_report', 'submitted_by', 'attendance_datetime'),
        }),
        ('Property & Inspection', {
            'fields': (
                'property_construction',
                'area_of_inspection',
                'pipe_construction',
            ),
        }),
        ('Discussion & Damage', {
            'fields': ('discussion_with_insured', 'resultant_damage'),
        }),
        ('Conclusion', {
            'fields': ('conclusion',),
        }),
        ('Snapshot (read-only)', {
            'fields': ('snapshot',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def job_id(self, obj):
        return obj.job_report.job.job_id
    job_id.short_description = 'Job ID'
    job_id.admin_order_field = 'job_report__job__job_id'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== LEAK INSPECTION ====================

@admin.register(LeakInspectionSubmission)
class LeakInspectionSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'job_id', 'submitted_by', 'attendance_datetime',
        'testing_location', 'tile_condition',
        'grout_condition', 'silicone_condition', 'created_at',
    ]
    list_filter = [
        'property_construction', 'testing_location',
        'tile_condition', 'grout_condition', 'silicone_condition',
    ]
    search_fields = ['job_report__job__job_id', 'submitted_by__email']
    readonly_fields = ['id', 'job_report', 'submitted_by', 'snapshot', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [ReportPhotoInline]

    fieldsets = (
        ('Job Reference', {
            'fields': ('id', 'job_report', 'submitted_by', 'attendance_datetime'),
        }),
        ('Property', {
            'fields': ('property_construction', 'testing_location'),
        }),
        ('Discussion & Damage', {
            'fields': ('discussion_with_site_contact', 'resultant_damage'),
        }),
        ('Pressure Tests', {
            'fields': (
                'pressure_cold_line', 'pressure_hot_line',
                'pressure_shower_breech', 'pressure_bath_breech',
            ),
        }),
        ('Flood & Spray Tests', {
            'fields': (
                'flood_test_shower', 'flood_test_bath',
                'spray_test_wall_tiles', 'spray_test_shower_screen',
            ),
        }),
        ('Condition Assessment', {
            'fields': (
                'tile_condition', 'grout_condition',
                'silicone_condition', 'silicone_around_spindles',
            ),
        }),
        ('Conclusion', {
            'fields': ('conclusion',),
        }),
        ('Snapshot (read-only)', {
            'fields': ('snapshot',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def job_id(self, obj):
        return obj.job_report.job.job_id
    job_id.short_description = 'Job ID'
    job_id.admin_order_field = 'job_report__job__job_id'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== SPRAY TEST ====================

@admin.register(SprayTestSubmission)
class SprayTestSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'job_id', 'submitted_by', 'attendance_datetime',
        'testing_location', 'flood_test', 'spray_test', 'created_at',
    ]
    list_filter = [
        'property_construction', 'testing_location',
        'flood_test', 'spray_test',
        'tile_condition', 'grout_condition', 'silicone_condition',
    ]
    search_fields = ['job_report__job__job_id', 'submitted_by__email']
    readonly_fields = ['id', 'job_report', 'submitted_by', 'snapshot', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [ReportPhotoInline]

    fieldsets = (
        ('Job Reference', {
            'fields': ('id', 'job_report', 'submitted_by', 'attendance_datetime'),
        }),
        ('Property', {
            'fields': ('property_construction', 'testing_location'),
        }),
        ('Discussion & Damage', {
            'fields': ('discussion_with_insured', 'resultant_damage'),
        }),
        ('Test Results', {
            'fields': (
                'flood_test', 'flood_test_notes',
                'spray_test', 'spray_test_notes',
            ),
        }),
        ('Condition Assessment', {
            'fields': (
                'tile_condition', 'tile_condition_notes',
                'grout_condition', 'grout_condition_notes',
                'silicone_condition', 'silicone_condition_notes',
            ),
        }),
        ('Conclusion', {
            'fields': ('conclusion',),
        }),
        ('Snapshot (read-only)', {
            'fields': ('snapshot',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def job_id(self, obj):
        return obj.job_report.job.job_id
    job_id.short_description = 'Job ID'
    job_id.admin_order_field = 'job_report__job__job_id'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ==================== REPORT PHOTO (standalone) ====================

@admin.register(ReportPhoto)
class ReportPhotoAdmin(admin.ModelAdmin):
    list_display = ['photo_type', 'content_type', 'object_id', 'photo_preview', 'uploaded_at']
    list_filter = ['photo_type', 'content_type']
    search_fields = ['photo_type', 'object_id']
    readonly_fields = ['content_type', 'object_id', 'photo_preview', 'uploaded_at']
    ordering = ['-uploaded_at']

    def photo_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:80px; border-radius:4px;" />',
                obj.image.url
            )
        return '—'
    photo_preview.short_description = 'Preview'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False