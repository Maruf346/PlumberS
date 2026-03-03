from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from hashlib import sha256
import uuid
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from subscriptions.models import SUBSCRIPTION_STATUS



class AuthProvider(models.TextChoices):
    SELF = 'self', 'Self'
    GOOGLE = 'google', 'Google'
    APPLE = 'apple', 'Apple'


class UserManager(BaseUserManager):
    use_in_migrations = True
    
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("You can't create user without an email address")
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        
        if not password:
            raise ValueError("Please set a password")
        user.set_password(password)
        user.save(using=self._db)
        
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is False:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is False:
            raise ValueError('Superuser must have is_superuser=True.')
        if extra_fields.get('is_active') is False:
            raise ValueError('Superuser must have is_active=True.')
        
        user = self.create_user(email, password, **extra_fields)
        
        # Create settings for superuser
        UserSettings.objects.get_or_create(user=user)
        
        return user
        

class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # Remove username field
    
    full_name = models.CharField(max_length=40)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    profile_picture = models.ImageField(upload_to='dps/', null=True, blank=True)
    phone = PhoneNumberField(verbose_name=_("Phone Number"), region=None, blank=True, null=True)
    
    is_active = models.BooleanField(default=False)
    is_premium = models.BooleanField(default=False)
    premium_expires_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # provider details
    provider = models.CharField(
        max_length=20,
        choices=AuthProvider.choices,
        default=AuthProvider.SELF
    )
    provider_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    def __str__(self):
        return f"Name: {self.full_name if self.full_name else 'John Doe'}"
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
        
    def update_premium_status(self):
        from subscriptions.models import UserSubscription, SUBSCRIPTION_STATUS
        
        active_subscription = UserSubscription.objects.filter(
            user=self.user,
            status=SUBSCRIPTION_STATUS.ACTIVE,
            end_date__gt=timezone.now()
        ).first()
        
        if active_subscription:
            self.is_premium = True
            self.premium_expires_at = active_subscription.end_date
        else:
            self.is_premium = False
            self.premium_expires_at = None
            
        self.save(update_fields=['is_premium', 'premium_expires_at'])
        
        

class UserSettings(models.Model):
    # class AppearanceChoice(models.TextChoices):
    #     LIGHT = 'light', 'Light'
    #     DARK = 'dark', 'Dark'
        
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='settings',
        primary_key=True
    )
    notification_enabled = models.BooleanField(default=True)
    # appearance = models.CharField(max_length=10, choices=AppearanceChoice.choices, default=AppearanceChoice.LIGHT)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f'Settings for {self.user.email}'
    
    class Meta:
        verbose_name = 'User Settings'
        verbose_name_plural = 'User Settings'
    