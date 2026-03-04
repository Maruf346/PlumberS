from django.contrib import admin
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'phone', 'email', 'contact_person_name', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'email', 'phone', 'contact_person_name']
    readonly_fields = ['id', 'maps_url', 'created_at', 'updated_at']