from rest_framework.serializers import ModelSerializer
from .models import *
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
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required',
            'invalid': 'Enter a valid email address'
        }
    )
    username = serializers.CharField(
        required=True,
        max_length=150,
        error_messages={'required': 'Username is required'}
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
    birth_date = serializers.DateField(
        required=True,
        error_messages={
            'invalid': 'Enter a valid date in YYYY-MM-DD format'
        }
    )
    # confirm_password = serializers.CharField(
    #     min_length=8,
    #     write_only=True,
    #     required=True,
    #     style={'input_type': 'password'},
    #     error_messages={
    #         'required': 'Password confirmation is required',
    #         'min_length': 'Password must be at least 8 characters'
    #     }
    # )
    
    def validate_email(self, value):
        value = value.lower().strip()    # strip() removes any leading, and trailing whitespaces
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('This email is already registered')
        return value
    
    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken')
        return value
    
    
    # def validate(self, data):
    #     # Validate passwords match and meet Django's password validators
    #     if data['password'] != data['confirm_password']:
    #         raise serializers.ValidationError({'confirm_password': "Passwords do not match"})
        
    #     # Validate password strength using Django's validators
    #     try:
    #         validate_password(data['password'])
    #     except DjangoValidationError as e:
    #         raise serializers.ValidationError({'password': list(e.messages)})
        
    #     return data


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

class UserSerializer(ModelSerializer):
    role = serializers.CharField(read_only=True)
    onboarding_complete = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'username', 'phone',
            'profile_picture', 'birth_date', 'is_active',
            'role', 'onboarding_complete',
            'provider', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_active', 'email', 'provider', 'created_at', 'updated_at']

    def get_onboarding_complete(self, obj):
        if obj.is_employee:
            try:
                return obj.employee_profile.onboarding_complete
            except EmployeeProfile.DoesNotExist:
                return False
        return True  # managers and admins skip onboarding



class UserProfileSerializer(ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'full_name', 
            'email', 'profile_picture',
            'is_active', 
            'phone', 'provider', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_active', 'email', 'provider', 'created_at', 'updated_at']


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
            # UserSettings.objects.create(user=user)
            
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
            # UserSettings.objects.create(user=user)
            
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
    
    


# NEW .......................................................


class EmergencyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyContact
        fields = ['id', 'name', 'mobile', 'relation']


class OnboardingStep1Serializer(serializers.ModelSerializer):
    """
    Step 1: Personal & professional details.
    full_name and phone go to User; rest go to EmployeeProfile.
    """
    full_name = serializers.CharField(max_length=100)
    phone = serializers.CharField()
    emergency_contact = EmergencyContactSerializer()

    class Meta:
        model = EmployeeProfile
        fields = [
            'full_name', 'phone',
            'primary_skill', 'employee_id',
            'profession', 'emergency_contact'
        ]

    def validate_employee_id(self, value):
        if value and EmployeeProfile.objects.filter(employee_id=value).exists():
            raise serializers.ValidationError('This Employee ID is already in use.')
        return value

    def update(self, instance, validated_data):
        # Update User fields
        user = instance.user
        user.full_name = validated_data.pop('full_name', user.full_name)
        user.phone = validated_data.pop('phone', user.phone)
        user.save()

        # Handle emergency contact
        ec_data = validated_data.pop('emergency_contact', None)
        if ec_data:
            if instance.emergency_contact:
                for attr, val in ec_data.items():
                    setattr(instance.emergency_contact, attr, val)
                instance.emergency_contact.save()
            else:
                ec = EmergencyContact.objects.create(**ec_data)
                instance.emergency_contact = ec

        # Update profile fields
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        return instance


class OnboardingStep2Serializer(serializers.ModelSerializer):
    """
    Step 2: Work & safety profile.
    Marks onboarding complete on save.
    """
    class Meta:
        model = EmployeeProfile
        fields = [
            'uses_company_vehicle',
            'drivers_license_number',
            'license_expiry_date',
            'drivers_license_file',
        ]

    def update(self, instance, validated_data):
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.onboarding_complete = True
        instance.save()
        return instance


class EmployeeProfileSerializer(serializers.ModelSerializer):
    # Full read serializer for employee profile (used in detail views).
    
    emergency_contact = EmergencyContactSerializer(read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    phone = serializers.CharField(source='user.phone', read_only=True)
    profile_picture = serializers.ImageField(source='user.profile_picture', read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = [
            'id', 'full_name', 'email', 'phone', 'profile_picture',
            'role', 'primary_skill', 'employee_id', 'profession',
            'emergency_contact', 'uses_company_vehicle',
            'drivers_license_number', 'license_expiry_date',
            'drivers_license_file', 'onboarding_complete',
            'created_at', 'updated_at'
        ]


class AdminCreateManagerSerializer(serializers.Serializer):
    # Admin uses this to create a manager account directly.
    
    first_name = serializers.CharField(max_length=50)
    last_name = serializers.CharField(max_length=50)
    profile_picture = serializers.ImageField(required=False)
    email = serializers.EmailField()
    phone = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)
    # department = serializers.CharField(required=False, allow_blank=True)
    # notes = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        # department = validated_data.pop('department', '')
        # notes = validated_data.pop('notes', '')
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        profile_picture = validated_data.pop('profile_picture', None)
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        phone = validated_data.pop('phone', '')

        user = User.objects.create_user(
            email=email,
            password=password,
            full_name=f"{first_name} {last_name}",
            profile_picture=profile_picture,
            phone=phone,
            is_staff=True,
            is_superuser=False,
            is_active=True,
        )
        ManagerProfile.objects.create(user=user)
        # UserSettings.objects.create(user=user)
        return user


class AdminEmployeeListSerializer(serializers.ModelSerializer):
    # Lightweight serializer for admin user list view.
    
    role = serializers.CharField(read_only=True)
    onboarding_complete = serializers.SerializerMethodField()
    primary_skill = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'username', 'phone',
            'profile_picture', 'is_active', 'role',
            'onboarding_complete', 'primary_skill',
            'created_at'
        ]

    def get_onboarding_complete(self, obj):
        try:
            return obj.employee_profile.onboarding_complete
        except EmployeeProfile.DoesNotExist:
            return False

    def get_primary_skill(self, obj):
        try:
            return obj.employee_profile.primary_skill
        except EmployeeProfile.DoesNotExist:
            return None
