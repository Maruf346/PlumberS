from celery import shared_task
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3) # Task will retry up to 3 times if it fails.
def send_registration_otp_email(self, email, otp, full_name):
    subject = 'Autointel Diagnostics App - Registration OTP'
    message = f'''
    Hi {full_name},

    Thank you for registering with Autointel Diagnostics App!

    Your OTP for email verification is: {otp}

    This OTP will expire in 5 minutes.

    If you didn't request this registration, please ignore this email.

    Best regards,
    Autointel Diagnostics Team
        '''
        
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        logger.info(f'Registration OTP sent successfully to {email}')
    except Exception as e:
        logger.error(f'Failed to send registration OTP to {email}: {str(e)}')
        
        # Retry with exponential backoff
        # | Retry | Delay |
        # | ----- | ----- |
        # | 1st   | 60s   |
        # | 2nd   | 120s  |
        # | 3rd   | 240s  |
        raise self.retry(e=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_password_reset_otp_email(self, email, otp, full_name):
    """
    Send OTP email for password reset
    """
    subject = 'Autointel Diagnostics App - Password Reset OTP'
    message = f'''
    Hi {full_name},

    We received a request to reset your password.

    Your OTP for password reset is: {otp}

    This OTP will expire in 10 minutes.

    If you didn't request this password reset, please ignore this email and ensure your account is secure.

    Best regards,
    Autointel Diagnostics Team
    '''
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,  # If email fails → raises an exception.
        )
        logger.info(f"Password reset OTP sent successfully to {email}")
    except Exception as e:
        logger.error(f"Failed to send password reset OTP to {email}: {str(e)}")
        raise self.retry(e=e, countdown=60 * (2 ** self.request.retries))
    

@shared_task
def send_welcome_email(email, full_name):
    # Send welcome email after successful registration
    
    subject = 'Welcome to Autointel Diagnostics!'
    message = f'''
    Hi {full_name},

    Welcome to Autointel Diagnostics App!

    Your account has been successfully created. You can now:
    - Register your vehicles
    - Track maintenance schedules
    - Get diagnostic alerts
    - And much more!

    Get started by adding your first vehicle.

    Best regards,
    Autointel Diagnostics Team
    '''
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,  # Don't fail registration if welcome email fails
        )
        logger.info(f'Welcome email sent to {email}')
    except Exception as e:
        logger.error(f'Failed to send welcome email to {email}: {str(e)}')