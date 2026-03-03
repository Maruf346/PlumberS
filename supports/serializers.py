from rest_framework import serializers
from .models import *
from user.serializers import UserSerializer


# List contacts for admin
class ListContactSupportSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = ContactSupport
        fields = [
            'id', 'user', 'user_details', 'subject', 
            'email', 'message', 'created_at'
        ]
        read_only_fields = fields
        
        
class CreateContactSupportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactSupport
        fields = [
            'subject', 'email', 'message'
        ]
        read_only_fields = ['id', 'user', 'created_at']
        
    def validate_email(self, value):
        return value.lower().strip()
    
    def validate_subject(self, value):
        value = value.strip()
        if len(value) < 5:
            raise serializers.ValidationError('Subject must be at least 5 characters')
        return value
    
    def validate_message(self, value):
        value = value.strip()
        if len(value) < 20:
            raise serializers.ValidationError("Message must be at least 20 characters")
        return value
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class FAQListSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = [
            'id', 'question',
            'answer', #, 'order', 
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
        

class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer']
        read_only_fields = ['id']
        
    def validate_question(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError("Question must be at least 10 characters")
        return value
    
    
class AboutUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AboutUs
        fields = ['content', 'updated_at']
        read_only_fields = ['updated_at']
        

class TermsAndConditionsSerializer(serializers.ModelSerializer):    
    class Meta:
        model = TermsAndConditions
        fields = [
            'content',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class PrivacyPolicySerializer(serializers.ModelSerializer):
    
    class Meta:
        model = PrivacyPolicy
        fields = [
            'content',
            'updated_at'
        ]
        read_only_fields = ['updated_at']