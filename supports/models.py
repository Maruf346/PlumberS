from django.db import models
import uuid
from django_ckeditor_5.fields import CKEditor5Field
from django.core.exceptions import ValidationError
from django.conf import settings



class ContactSupport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey('user.User', on_delete=models.CASCADE, related_name='support_requests')
    subject = models.CharField(max_length=255, help_text='Short title of your issue')
    email = models.EmailField(help_text='Write your email')
    message = models.TextField(help_text='Please explain what happened...')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Contact Support'
        verbose_name_plural = 'Contact Support Requests'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Message: {self.subject}'
    

class FAQ(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.CharField(max_length=500)
    answer = models.CharField(max_length=500)
    # order = models.PositiveIntegerField(
    #     default=0,
    #     help_text='Order in which FAQs appear (lower numbers first)'
    # )
    # is_active = models.BooleanField(
    #     default=True,
    #     help_text='Whether this FAQ is visible to users'
    # )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'
        ordering = ['-created_at']
        
    def __str__(self):
        return self.question
    

class AboutUs(models.Model):
    content = CKEditor5Field('Content', config_name='extends')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'About Us'
        verbose_name_plural = 'About Us'
        
    def save(self, *args, **kwargs):
        # Singleton
        if not self.pk and AboutUs.objects.exists():
            raise ValidationError('Only one About Us instance allowed.')
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return 'About Us Content'
    
    
class TermsAndConditions(models.Model):
    content = CKEditor5Field('Content', config_name='extends')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Terms and Conditions'
        verbose_name_plural = 'Terms and Conditions'
        
    def save(self, *args, **kwargs):
        # Singleton
        if not self.pk and TermsAndConditions.objects.exists():
            raise ValidationError('Only one Terms & Conditions instance allowed.')
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return 'Terms and Conditions'

    
class PrivacyPolicy(models.Model):
    content = CKEditor5Field('Content', config_name='extends')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Privacy Policy'
        verbose_name_plural = 'Privacy Policy'
    
    def save(self, *args, **kwargs):
        # Singleton
        if not self.pk and PrivacyPolicy.objects.exists():
            raise ValidationError("Only one Privacy Policy instance allowed.")
        return super().save(*args, **kwargs)
    
    def __str__(self):
        return 'Privacy Policy'
    
    
class Feedback(models.Model):
    """
    Submitted by any authenticated employee.
    User is automatically linked from request.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='feedbacks'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    country = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=100, blank=True)
    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Feedback from {self.first_name} {self.last_name} ({self.email})"

    class Meta:
        verbose_name = 'Feedback'
        verbose_name_plural = 'Feedbacks'
        ordering = ['-created_at']


class IssueReport(models.Model):
    """
    Issue report submitted by any authenticated employee.
    Up to 5 optional photos. User is automatically linked from request.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='issue_reports'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()

    # Up to 5 optional photos — separate fields are cleaner than
    # a related model for a fixed small number like this
    photo_1 = models.ImageField(upload_to='issues/', null=True, blank=True)
    photo_2 = models.ImageField(upload_to='issues/', null=True, blank=True)
    photo_3 = models.ImageField(upload_to='issues/', null=True, blank=True)
    photo_4 = models.ImageField(upload_to='issues/', null=True, blank=True)
    photo_5 = models.ImageField(upload_to='issues/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Issue: {self.title} by {self.user}"

    @property
    def photos(self):
        """Returns a list of only the uploaded photo URLs, skipping empty ones."""
        result = []
        for field in [self.photo_1, self.photo_2, self.photo_3, self.photo_4, self.photo_5]:
            if field:
                result.append(field)
        return result

    @property
    def photo_count(self):
        return len(self.photos)

    class Meta:
        verbose_name = 'Issue Report'
        verbose_name_plural = 'Issue Reports'
        ordering = ['-created_at']