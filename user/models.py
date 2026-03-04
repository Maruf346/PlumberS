from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from hashlib import sha256
import uuid
from phonenumber_field.modelfields import PhoneNumberField
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class AuthProvider(models.TextChoices):
    SELF = 'self', 'Self'
    GOOGLE = 'google', 'Google'
    APPLE = 'apple', 'Apple'


class PrimarySkill(models.TextChoices):
    PLUMBING = 'plumbing', 'Plumbing'
    GASFITTING = 'gasfitting', 'Gasfitting'
    DRAINAGE = 'drainage', 'Drainage'
    ROOFING = 'roofing', 'Roofing'
    HVAC = 'hvac', 'HVAC'
    ELECTRICAL = 'electrical', 'Electrical'
    GENERAL = 'general', 'General Maintenance'
    OTHER = 'other', 'Other'


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
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Remove default username, use our own
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    first_name = None  # We use full_name instead
    last_name = None

    full_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    profile_picture = models.ImageField(upload_to='dps/', null=True, blank=True)
    phone = PhoneNumberField(verbose_name=_("Phone Number"), region=None, blank=True, null=True)
    birth_date = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # provider details
    provider = models.CharField(
        max_length=20,
        choices=AuthProvider.choices,
        default=AuthProvider.SELF
    )
    provider_id = models.CharField(max_length=255, null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    # Role helpers
    @property
    def role(self):
        if self.is_superuser:
            return 'admin'
        elif self.is_staff:
            return 'manager'
        return 'employee'

    @property
    def is_employee(self):
        return not self.is_staff and not self.is_superuser

    @property
    def is_manager(self):
        return self.is_staff and not self.is_superuser

    @property
    def is_admin(self):
        return self.is_superuser

    def __str__(self):
        return f"{self.full_name or self.email} ({self.role})"

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']


class EmergencyContact(models.Model):
    # Emergency contact for an employee.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    mobile = PhoneNumberField(verbose_name=_("Mobile Number"))
    relation = models.CharField(max_length=100, help_text="e.g. Wife, Father, Friend")

    def __str__(self):
        return f"{self.name} ({self.relation})"


class EmployeeProfile(models.Model):
    # Extended profile for employees (plumbers/technicians).
    # Created after onboarding is completed.
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='employee_profile'
    )

    # Onboarding step 1 fields
    primary_skill = models.CharField(
        max_length=50,
        choices=PrimarySkill.choices,
        blank=True
    )
    employee_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    profession = models.CharField(max_length=100, blank=True)
    emergency_contact = models.OneToOneField(
        EmergencyContact,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_profile'
    )

    # Onboarding step 2 — work & safety details
    uses_company_vehicle = models.BooleanField(default=False)
    drivers_license_number = models.CharField(max_length=50, blank=True, null=True)
    license_expiry_date = models.DateField(null=True, blank=True)
    drivers_license_file = models.FileField(
        upload_to='licenses/',
        null=True,
        blank=True,
        help_text="Upload driving license (PDF or image)"
    )

    # Onboarding tracking
    onboarding_complete = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.email}"

    class Meta:
        verbose_name = 'Employee Profile'
        verbose_name_plural = 'Employee Profiles'


class ManagerProfile(models.Model):
   # Extended profile for managers.
    # Created by admin when creating a manager account.

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='manager_profile'
    )
    department = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Manager: {self.user.email}"


# class UserSettings(models.Model):
#     # App-level settings per user. 
#     user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
#     # To add existing settings fields here if any
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return f"Settings: {self.user.email}"