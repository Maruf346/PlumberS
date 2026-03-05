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
        
        
# ==================== FEEDBACK ====================

class FeedbackSubmitSerializer(serializers.ModelSerializer):
    """Employee submits feedback. user is set automatically in the view."""

    class Meta:
        model = Feedback
        fields = [
            'id', 'first_name', 'last_name',
            'email', 'phone', 'country',
            'language', 'message',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate_email(self, value):
        return value.lower().strip()


class FeedbackListSerializer(serializers.ModelSerializer):
    """Lightweight — for admin list view."""
    submitted_by = serializers.CharField(source='user.full_name', read_only=True)
    submitted_by_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Feedback
        fields = [
            'id', 'first_name', 'last_name', 'email',
            'submitted_by', 'submitted_by_email',
            'country', 'language', 'created_at'
        ]


class FeedbackDetailSerializer(serializers.ModelSerializer):
    """Full detail — for admin retrieve view."""
    submitted_by = serializers.CharField(source='user.full_name', read_only=True)
    submitted_by_id = serializers.UUIDField(source='user.id', read_only=True)
    submitted_by_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = Feedback
        fields = [
            'id', 'submitted_by', 'submitted_by_id', 'submitted_by_email',
            'first_name', 'last_name', 'email', 'phone',
            'country', 'language', 'message',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


# ==================== ISSUE REPORT ====================

class IssueReportSubmitSerializer(serializers.ModelSerializer):
    """
    Employee submits an issue report with up to 5 photos.
    user is set automatically in the view.
    """

    class Meta:
        model = IssueReport
        fields = [
            'id', 'title', 'description',
            'photo_1', 'photo_2', 'photo_3',
            'photo_4', 'photo_5',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def validate(self, data):
        # Ensure at least title and description are present
        if not data.get('title', '').strip():
            raise serializers.ValidationError({'title': 'Title is required.'})
        if not data.get('description', '').strip():
            raise serializers.ValidationError({'description': 'Description is required.'})
        return data


class IssueReportListSerializer(serializers.ModelSerializer):
    """Lightweight — for admin list view."""
    submitted_by = serializers.CharField(source='user.full_name', read_only=True)
    submitted_by_email = serializers.CharField(source='user.email', read_only=True)
    photo_count = serializers.ReadOnlyField()

    class Meta:
        model = IssueReport
        fields = [
            'id', 'title', 'submitted_by',
            'submitted_by_email', 'photo_count',
            'created_at'
        ]


class IssueReportDetailSerializer(serializers.ModelSerializer):
    """Full detail — for admin retrieve view."""
    submitted_by = serializers.CharField(source='user.full_name', read_only=True)
    submitted_by_id = serializers.UUIDField(source='user.id', read_only=True)
    submitted_by_email = serializers.CharField(source='user.email', read_only=True)
    photo_count = serializers.ReadOnlyField()

    class Meta:
        model = IssueReport
        fields = [
            'id', 'submitted_by', 'submitted_by_id', 'submitted_by_email',
            'title', 'description',
            'photo_1', 'photo_2', 'photo_3', 'photo_4', 'photo_5',
            'photo_count', 'created_at', 'updated_at'
        ]
        read_only_fields = fields