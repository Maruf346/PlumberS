from rest_framework import serializers
from .models import Certificate


class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = [
            'id', 'name', 'issuing_organization', 'description',
            'issue_date', 'expiration_date', 'media',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, data):
        issue_date = data.get('issue_date')
        expiration_date = data.get('expiration_date')
        if issue_date and expiration_date and expiration_date < issue_date:
            raise serializers.ValidationError(
                {'expiration_date': 'Expiration date cannot be before issue date.'}
            )
        return data


class AdminCertificateSerializer(serializers.ModelSerializer):
    # Read-only serializer for admin — includes owner info.
    owner_email = serializers.EmailField(source='user.email', read_only=True)
    owner_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = Certificate
        fields = [
            'id', 'owner_email', 'owner_name',
            'name', 'issuing_organization', 'description',
            'issue_date', 'expiration_date', 'media',
            'created_at', 'updated_at'
        ]