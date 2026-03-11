from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, EmployeeProfile, ManagerProfile, EmergencyContact


class EmployeeProfileInline(admin.StackedInline):
    model = EmployeeProfile
    can_delete = False
    verbose_name_plural = 'Employee Profile'
    fk_name = 'user'
    fields = [
        'primary_skill', 'employee_id', 'profession', 'emergency_contact',
        'uses_company_vehicle', 'drivers_license_number',
        'license_expiry_date', 'drivers_license_file', 'onboarding_complete'
    ]


class ManagerProfileInline(admin.StackedInline):
    model = ManagerProfile
    can_delete = False
    verbose_name_plural = 'Manager Profile'
    fk_name = 'user'
    fields = ['notes']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['-created_at']
    list_display = [
        'email', 'full_name', 'role', 'is_active',
        'provider', 'onboarding_complete_display', 'created_at'
    ]
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'provider']
    search_fields = ['email', 'full_name', 'username', 'phone']
    readonly_fields = ['id', 'created_at', 'updated_at', 'provider', 'provider_id']

    fieldsets = (
        (None, {
            'fields': ('id', 'email', 'password')
        }),
        ('Personal Info', {
            'fields': ('full_name', 'username', 'phone', 'birth_date', 'profile_picture')
        }),
        ('Auth Provider', {
            'fields': ('provider', 'provider_id'),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'full_name', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )

    def get_inlines(self, request, obj=None):
        if obj is None:
            return []
        if obj.is_employee:
            return [EmployeeProfileInline]
        if obj.is_manager:
            return [ManagerProfileInline]
        return []

    @admin.display(description='Onboarding', boolean=True)
    def onboarding_complete_display(self, obj):
        if obj.is_employee:
            try:
                return obj.employee_profile.onboarding_complete
            except EmployeeProfile.DoesNotExist:
                return False
        return True  # managers and admins skip onboarding


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'employee_id', 'primary_skill',
        'profession', 'onboarding_complete', 'uses_company_vehicle'
    ]
    list_filter = ['primary_skill', 'onboarding_complete', 'uses_company_vehicle']
    search_fields = ['user__email', 'user__full_name', 'employee_id', 'profession']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user', 'emergency_contact']

    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Professional Info', {
            'fields': ('employee_id', 'primary_skill', 'profession')
        }),
        ('Emergency Contact', {
            'fields': ('emergency_contact',)
        }),
        ('Vehicle & License', {
            'fields': (
                'uses_company_vehicle', 'drivers_license_number',
                'license_expiry_date', 'drivers_license_file'
            )
        }),
        ('Onboarding', {
            'fields': ('onboarding_complete',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ManagerProfile)
class ManagerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at']
    search_fields = ['user__email', 'user__full_name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['user']


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ['name', 'relation', 'mobile', 'linked_employee']
    search_fields = ['name', 'mobile']
    list_filter = ['relation']

    @admin.display(description='Employee')
    def linked_employee(self, obj):
        try:
            return obj.employee_profile.user.email
        except EmployeeProfile.DoesNotExist:
            return '—'