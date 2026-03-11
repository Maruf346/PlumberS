import random
import string
from django.core.cache import cache
from user.models import User, AuthProvider
from django.contrib.auth.hashers import make_password
from django.conf import settings
import secrets


class OTPService:
    # Service for OTP generation and validation
    
    @staticmethod
    def generate_otp(length=6):
        # numeric OTP
        return ''.join(random.choices(string.digits, k=length))
    
    @staticmethod
    def store_otp(cache_key, otp, expiry_seconds):
        # stores OTP in Redis
        cache.set(cache_key, otp, expiry_seconds)
        
    @staticmethod
    def verify_otp(cache_key, provided_otp):
        # verify and then delete OTP
        stored_otp = cache.get(cache_key)
        
        if not stored_otp:
            return False, 'OTP expired or not found'
        
        if stored_otp != provided_otp:
            return False, 'Invalid OTP'
        
        # OTP is valid, delete it (one-time use)
        cache.delete(cache_key)
        return True, 'OTP verified'
    

class RegistrationService:
    # Service for user signup with OTP verification
    
    @staticmethod
    def initiate_registration(email, password, username, birth_date=None):
        if User.objects.filter(email=email).exists():
            raise ValueError('Email already registered')
        if User.objects.filter(username__iexact=username).exists():
            raise ValueError('Username already taken')

        # Generate OTP
        otp = OTPService.generate_otp()
        
        # store reg. data in Redis
        cache_key = f'registration_otp:{email}'
        registration_data = {
            'email': email,
            'username': username,
            'birth_date': str(birth_date) if birth_date else None,
            'password': make_password(password),
            'otp': otp
        }
        cache.set(cache_key, registration_data, settings.OTP_EXPIRY_SECONDS)

        try:
            from user.tasks import send_registration_otp_email
            send_registration_otp_email.delay(email, otp, username)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to queue OTP email: {str(e)}")
            # Don't raise — OTP is already stored in Redis, user can retry

        return {
            'message': 'OTP sent to your email. Please verify to complete registration.',
            'email': email,
            'expires_in_seconds': settings.OTP_EXPIRY_SECONDS
        }


    @staticmethod
    def verify_and_complete_registration(email, otp):
        cache_key = f'registration_otp:{email}'
        registration_data = cache.get(cache_key)

        if not registration_data:
            raise ValueError('OTP expired or invalid email')
        if registration_data['otp'] != otp:
            raise ValueError('Invalid OTP')

        # Create user account
        from datetime import date
        birth_date = None
        if registration_data.get('birth_date'):
            birth_date = date.fromisoformat(registration_data['birth_date'])

        user = User.objects.create(
            email=email,
            username=registration_data['username'],
            birth_date=birth_date,
            password=registration_data['password'],
            is_active=True,
            provider=AuthProvider.SELF,
            is_staff=False,
            is_superuser=False,
        )

        # Create empty employee profile (onboarding not complete yet)
        from user.models import EmployeeProfile
        EmployeeProfile.objects.create(user=user, onboarding_complete=False)

        # UserSettings.objects.create(user=user)
        cache.delete(cache_key)

        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        return {
            'user': user,
            'refresh_token': str(refresh),
            'access_token': str(refresh.access_token)
        }
        
        
class PasswordResetService:
    # Service for password reset with OTP verification
    
    @staticmethod
    def initiate_password_reset(email):
        # Send OTP for password reset
        
        # Check if user exists (but don't reveal)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return {
                'message': 'If the mail exists, an OTP has been sent',
                'expires_in_seconds': settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS
            }
        
        otp = OTPService.generate_otp()
        
        # Store OTP in Redis
        cache_key = f'password_reset_otp:{email}'
        cache.set(cache_key, otp, settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS)
        
        # Send OTP email
        from user.tasks import send_password_reset_otp_email
        send_password_reset_otp_email.delay(email, otp, user.full_name)
        
        return {
            'message': 'If the email exists, an OTP has been sent',
            'expires_in_seconds': settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS
        }
        
    @staticmethod
    def verify_reset_otp(email, otp):
        cache_key = f'password_reset_otp:{email}'
        stored_otp = cache.get(cache_key)
        
        if not stored_otp:
            raise ValueError('OTP expired or not found')
        
        if stored_otp != otp:
            raise ValueError('Invalid OTP')
        
        # Generate reset token
        reset_token = secrets.token_urlsafe(32) # Cryptographically secure token.
        
        # Store reset token in Redis
        token_key = f'password_reset_token:{reset_token}'
        cache.set(
            token_key,
            email,
            settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS
        )
        
        # Delete OTP (one-time use)
        cache.delete(cache_key)
        
        return {
            'reset_token': reset_token,
            'message': 'OTP verified. You can now reset your password.',
            'expires_in_seconds': settings.PASSWORD_RESET_TOKEN_EXPIRY_SECONDS
        }
        
    @staticmethod
    def reset_password(reset_token, new_password):
        # Reset pass using token
        
        token_key = f'password_reset_token:{reset_token}'
        email = cache.get(token_key)
        
        if not email:
            raise ValueError("Invalid or expired reset token")
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise ValueError("User not found")
        
        # Update pass
        user.set_password(new_password)
        user.save()
        
        # Delete reset token
        cache.delete(token_key)
        
        # Optional: Invalidate all existing tokens (force re-login)
        from rest_framework_simplejwt.tokens import RefreshToken
        # This forces user to login again with new password
        
        return {
            'message': 'Password reset successful. Please login with your new password.',
            'user_id': str(user.id)
        }
        
        