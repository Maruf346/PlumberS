from rest_framework import serializers
from .models import Client


class ClientSerializer(serializers.ModelSerializer):
    # Full serializer — used for create/update by admin.
    # maps_url is read-only, derived from address.

    maps_url = serializers.ReadOnlyField()

    class Meta:
        model = Client
        fields = [
            'id', 'name', 'phone', 'email',
            'profile_picture', 'address', 'maps_url',
            'contact_person_name', 'site_access',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'maps_url', 'created_at', 'updated_at']

    def validate_phone(self, value):
        value = value.strip()
        if value and not value.replace('+', '').replace(' ', '').replace('-', '').isdigit():
            raise serializers.ValidationError('Enter a valid phone number.')
        return value


class ClientListSerializer(serializers.ModelSerializer):
    # Lightweight serializer for list views.
    # Employees and managers see this — no site_access exposed.

    maps_url = serializers.ReadOnlyField()

    class Meta:
        model = Client
        fields = [
            'id', 'name', 'phone', 'email',
            'profile_picture', 'address', 'maps_url',
            'contact_person_name', 'is_active'
        ]


class ClientDetailSerializer(serializers.ModelSerializer):
    # Full read serializer for retrieve — includes site_access.
    # Used by all authenticated staff (they need gate codes when on a job).

    maps_url = serializers.ReadOnlyField()

    class Meta:
        model = Client
        fields = [
            'id', 'name', 'phone', 'email',
            'profile_picture', 'address', 'maps_url',
            'contact_person_name', 'site_access',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = fields