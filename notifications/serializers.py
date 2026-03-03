from rest_framework import serializers
from .models import *



class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'title',
            'body',
            'data',
            'priority',
            'is_read',
            'read_at',
            'created_at'
        ]
        read_only_fields = fields
        
        
class NotificationMarkReadSerializer(serializers.Serializer):
    notification_id = serializers.UUIDField(required=True)
    
    
class FCMTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMToken
        fields = ['token', 'device_type', 'device_name']
    
    def validate_token(self, value):
        # Ensure token is not empty
        if not value or len(value) < 10:
            raise serializers.ValidationError("Invalid FCM token")
        return value
    
    def create(self, validated_data):
        # Create or update FCM token
        user = self.context['request'].user
        token = validated_data['token']
        
        # Check if token already exists
        fcm_token, created = FCMToken.objects.update_or_create(
            token=token,
            defaults={
                'user': user,
                'device_type': validated_data['device_type'],
                'device_name': validated_data.get('device_name', ''),
                'is_active': True
            }
        )
        
        return fcm_token


class FCMTokenDeleteSerializer(serializers.Serializer):
    token = serializers.CharField(required=True)