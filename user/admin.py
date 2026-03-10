from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, EmployeeProfile, ManagerProfile, EmergencyContact


class UserAdmin(BaseUserAdmin):
    # Use email instead of username
    list_display = ('email', 'full_name', 'role', 'provider', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'provider')
    search_fields = ('email', 'full_name', 'phone')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'username', 'profile_picture', 'phone', 'birth_date')}),
        ('Provider', {'fields': ('provider', 'provider_id')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_superuser', 'is_active'),
        }),
    )


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'primary_skill', 'employee_id', 'onboarding_complete', 'created_at')
    list_filter = ('primary_skill', 'onboarding_complete', 'uses_company_vehicle')
    search_fields = ('user__email', 'employee_id', 'profession')
    ordering = ('-created_at',)


@admin.register(ManagerProfile)
class ManagerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__email',)
    ordering = ('-created_at',)


@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile', 'relation')
    search_fields = ('name', 'relation', 'mobile')


# Register the custom User model with the custom admin
admin.site.register(User, UserAdmin)
