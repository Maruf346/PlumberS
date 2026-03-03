from rest_framework.serializers import ModelSerializer
from .models import User, AuthProvider, UserSettings
from rest_framework import serializers
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model, authenticate
from jwt.algorithms import RSAAlgorithm
import jwt
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import datetime
import logging

# OAuth2 imports
from google.oauth2 import id_token
from google.auth.transport import requests
import requests as req
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.files.base import ContentFile

from notifications.services import NotificationTemplates

logger = logging.getLogger(__name__)
User = get_user_model()

# ==================== REGISTRATION SERIALIZERS ====================
class InitiateRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(
        max_length=40,
        required=True,
        error_messages={
            'required': 'Full name is required',
            'blank': 'Full name cannot be blank'
        }
    )
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required',
            'invalid': 'Enter a valid email address'
        }
    )
    password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'Password is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    confirm_password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'Password confirmation is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    
    def validate_email(self, value):
        value = value.lower().strip()    # strip() removes any leading, and trailing whitespaces
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('This email is already registered')
        return value
    
    def validate_full_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError('Full name must be at least 2 characters')
        return value
    
    def validate(self, data):
        # Validate passwords match and meet Django's password validators
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': "Passwords do not match"})
        
        # Validate password strength using Django's validators
        try:
            validate_password(data['password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        
        return data


class VerifyRegistrationOTPSerializer(serializers.Serializer):
    # Serializer for verifying OTP and completing registration
    
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required',
            'invalid': 'Enter a valid email address'
        }
    )
    otp = serializers.CharField(
        min_length = 6,
        max_length = 6,
        required = True,
        error_messages={
            'required': 'OTP is required',
            'min_length': 'OTP must be 6 digits',
            'max_length': 'OTP must be 6 digits'
        }
    )
    
    def validate_email(self, value):
        return value.lower().strip()
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('OTP must contain only numbers')
        return value
    
    
# ==================== PASSWORD RESET SERIALIZERS ====================

class InitiatePasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required',
            'invalid': 'Enter a valid email address'
        }
    )
    
    def validate_email(self, value):
        return value.lower().strip()
    

class VerifyPasswordResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required',
            'invalid': 'Enter a valid email address'
        }
    )
    otp = serializers.CharField(
        min_length=6,
        max_length=6,
        required=True,
        error_messages={
            'required': 'OTP is required',
            'min_length': 'OTP must be 6 digits',
            'max_length': 'OTP must be 6 digits'
        }
    )
    
    def validate_email(self, value):
        return value.lower().strip()
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only numbers")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    # Serializer for resetting password with token
    reset_token = serializers.CharField(
        required=True,
        error_messages={
            'required': 'Reset token is required'
        }
    )
    new_password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'New password is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    confirm_new_password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'Password confirmation is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    
    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({
                'confirm_new_password': "Passwords do not match"
            })
        
        # Validate password strength
        try:
            validate_password(data['new_password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})
        
        return data


# ==================== USER SERIALIZERS ====================

# For admin: To manually approve users
class UserApprovalSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'profile_picture', 
            'phone', 'is_active', 'is_premium', 'provider',
            'created_at', 'updated_at'
            ]
        read_only_fields = ['id', 'full_name', 'email', 'profile_picture', 'phone', 'is_premium', 'provider', 'created_at', 'updated_at']
        

class UserSerializer(ModelSerializer):
    
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'phone',
            'profile_picture', 'is_active', 'is_premium',
            'provider', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'is_active', 'is_premium', 'email',
            'provider', 'created_at', 'updated_at'
        ]


class UserSettingsSerializer(ModelSerializer):
    # Serializer for UserSettings model
    
    class Meta:
        model = UserSettings
        fields = [
            'notification_enabled',
            # 'appearance',
            'updated_at'
        ]
        read_only_fields = ['updated_at']


class UserProfileSerializer(ModelSerializer):
    settings = UserSettingsSerializer(read_only=True)
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 
            'email', 'profile_picture',
            'is_active', 'is_premium',
            'phone', 'provider', 
            'created_at', 'updated_at', 'settings',
        ]
        read_only_fields = ['id', 'is_active', 'email', 'is_premium', 'provider', 'created_at', 'updated_at']


class AdminProfileSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'phone',
            'profile_picture', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'created_at', 'updated_at']
        
        
class UserLoginSerializer(ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ('email', 'password')

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            raise serializers.ValidationError({
                "detail": "Email and password are required."
            })

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                "detail": "Invalid email or password."
            })

        # Check password first
        if not user.check_password(password):
            raise serializers.ValidationError({
                "detail": "Invalid email or password."
            })

        # Then check active
        if not user.is_active:
            raise serializers.ValidationError({
                "detail": "User account is disabled."
            })

        data['user'] = user
        return data    
        

class AdminLoginSerializer(UserLoginSerializer):
    def validate(self, data):
        data = super().validate(data)
        user = data['user']
        
        if not user.is_staff:
            raise serializers.ValidationError({
                "detail": "Admin access required."
            })
        
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'Current password is required'
        }
    )
    new_password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'New password is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    confirm_new_password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'Password confirmation is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value
    
    def validate_new_password(self, value):
        old_password = self.initial_data.get('old_password')
        
        if old_password and value == old_password:
            raise serializers.ValidationError(
                "New password must be different from current password"
            )
        return value
    
    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({
                'confirm_new_password': "Passwords do not match"
            })
        
        # Validate password strength using Django's validators
        try:
            validate_password(data['new_password'], self.context['request'].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({
                'new_password': list(e.messages)
            })
        
        return data
    

class GoogleOAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True)
    
    def validate(self, attrs):
        token = attrs.get('id_token')
        
        try:
            google_user = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                settings.GOOGLE_WEB_CLIENT_ID   # For mobile: Web client id is req.
            )
        except Exception:
            raise serializers.ValidationError("Invalid or expired Google token")
        
        # Check if email is verified
        # if not google_user.get('email_verified'):
        #     raise serializers.ValidationError('Google email not verified')
        
        # Extarct data from google response
        email = google_user.get('email')
        if not email:
            raise serializers.ValidationError(
                "Google account has no email. Please use another login method."
            )
            
        first_name = google_user.get('given_name', '')
        last_name = google_user.get('family_name', '')
        picture = google_user.get('picture', '')
        provider_id = google_user.get('sub')
        
        user, created = User.objects.get_or_create(
            email = email,
            defaults={
                'full_name': google_user.get("name") or f"{first_name} {last_name}".strip(),
                'is_active': False,
                'provider': AuthProvider.GOOGLE,
                'provider_id': provider_id
            },
        )
                
        if created:
            user.set_unusable_password()
            if picture:
                try:
                    pic = req.get(picture, timeout=5)
                    pic.raise_for_status()
                
                    # if pic.status_code == 200:  // For web
                    file_name = f'{user.id}_google.jpg'
                    user.profile_picture.save(
                        file_name,
                        ContentFile(pic.content),
                        save=False
                    )
                except Exception:
                    pass
            user.save()
            UserSettings.objects.create(user=user)
            
            try: 
                # Send welcome email asynchronously
                from user.tasks import send_welcome_email
                send_welcome_email.delay(user.email, user.full_name)
                
                # Send welcome notification
                NotificationTemplates.welcome(user)
                
                # Notify admins
                NotificationTemplates.new_user_joined(user)
            except Exception as e:
                logger.error(f"Failed to send Google login notifications: {str(e)}")
            
        if not created:
            if user.provider == AuthProvider.SELF:
                raise serializers.ValidationError('Account already exists. Please login with email and password')
            elif user.provider != AuthProvider.GOOGLE:
                raise serializers.ValidationError(f'Account already exists. Please login with {user.provider}.')
        
        refresh = RefreshToken.for_user(user)
        
        return {
            'user': UserProfileSerializer(user).data,
            # 'is_new_user': created,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }
        }

      
class AppleOAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=True)
    user = serializers.JSONField(required=False)
    
    def validate(self, attrs):
        id_token_value = attrs.get('id_token')
        user_data = attrs.get('user', {})
        
        # Fetch Apple public keys
        apple_public_keys = req.get('https://appleid.apple.com/auth/keys').json()
        
        # Extracts metadata from token [includes: kid; (key id)]
        header = jwt.get_unverified_header(id_token_value)
        
        # Match correct public key [Apple rotates keys]
        # This finds the exact key used to sign this token
        key = next(
            k for k in apple_public_keys['keys']
            if k['kid'] == header['kid']
        )
        
        # Convert JWK → RSA public key
        public_key = RSAAlgorithm.from_jwk(key)
        
        # Decode & verify token
        payload = jwt.decode(
            id_token_value,
            public_key,
            algorithms=['RS256'],
            audience=settings.APPLE_CLIENT_ID
        )
        
        # Extract user data
        email = payload.get('email')
        provider_id = payload.get('sub')    # sub → unique Apple user ID
        full_name = user_data.get('name') if user_data else email.split('@')[0]
        
        if not email:
            raise serializers.ValidationError('Apple account has no email.')
        
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'full_name': full_name,
                'is_active': False,
                'provider': AuthProvider.APPLE,
                'provider_id': provider_id
            }
        )
        
        if created:
            user.set_unusable_password()
            user.save()
            UserSettings.objects.create(user=user)
            
            try: 
                # Send welcome email asynchronously
                from user.tasks import send_welcome_email
                send_welcome_email.delay(user.email, user.full_name)
                
                # Send welcome notification
                NotificationTemplates.welcome(user)
                
                # Notify admins
                NotificationTemplates.new_user_joined(user)
            except Exception as e:
                logger.error(f"Failed to send Apple login notifications: {str(e)}")
        
        if not created:
            if user.provider == AuthProvider.SELF:
                raise serializers.ValidationError('Account already exists. Please login with email and password')
            if user.provider != AuthProvider.APPLE:
                raise serializers.ValidationError(f'Account already exists. Please login with {user.provider}')
            
        refresh = RefreshToken.for_user(user)
        
        return {
            'user': UserProfileSerializer(user).data,
            # 'is_new_user': created,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }
        }
        
        
# ==================== AUTHENTICATION RESPONSE SERIALIZERS ====================

class AuthTokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserSerializer()
    
    
class RegistrationResponseSerializer(serializers.Serializer):
    # Serializer for registration completion response
    message = serializers.CharField()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserSerializer()
    
    
# Admin dashboard serializers
class UserStatsInputSerializer(serializers.Serializer):
    year = serializers.IntegerField(
        required=True,
        min_value=2026,
        max_value=datetime.now().year,
        error_messages={
            'required': 'Year parameter is required',
            'invalid': 'Year must be a valid integer',
            'min_value': 'Year must be 2026 (App Launch) or later',
            'max_value': f'Year cannot be greater than current year [{datetime.now().year}]'
        }
    )
    
    def validate_year(self, value):
        current_year = datetime.now().year
        if value > current_year:
            raise serializers.ValidationError(f'Year cannot be greater than current year {current_year}')
        return value


class MonthlyUserCountSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    month_name = serializers.CharField()
    count = serializers.IntegerField()
    
    
class YearlyUserGrowthSerializer(serializers.Serializer):
    year = serializers.IntegerField()
    total_users = serializers.IntegerField()
    monthly_counts = MonthlyUserCountSerializer(many=True)
