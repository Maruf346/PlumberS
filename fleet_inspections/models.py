from django.db import models
from django.conf import settings
import uuid


class CheckItemCategory(models.TextChoices):
    LIGHTS = 'lights', 'Lights'
    TIRES = 'tires', 'Tires'
    BRAKES = 'brakes', 'Brakes'
    FLUID_LEVELS = 'fluid_levels', 'Fluid Levels'
    MIRRORS = 'mirrors', 'Mirrors'
    HORN = 'horn', 'Horn'
    WINDSHIELD_WIPERS = 'windshield_wipers', 'Windshield & Wipers'
    DASHBOARD_WARNING_LIGHTS = 'dashboard_warning_lights', 'Dashboard Warning Lights'
    BODY_EXTERIOR = 'body_exterior', 'Body Exterior'


class VehicleInspection(models.Model):
    """
    A completed inspection submitted all at once.
    No draft state — created only on final submission.
    has_open_issue is computed from check items on save.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        'fleets.Vehicle',
        on_delete=models.CASCADE,
        related_name='inspections'
    )
    inspected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='inspections'
    )
    has_open_issue = models.BooleanField(
        default=False,
        help_text="True if any check item has is_ok=False."
    )
    notes = models.TextField(blank=True)
    inspected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vehicle.name} — {self.inspected_by} — {self.inspected_at}"

    @property
    def completed_items_count(self):
        return self.check_items.count()

    @property
    def issue_count(self):
        return self.check_items.filter(is_ok=False).count()

    class Meta:
        verbose_name = 'Vehicle Inspection'
        verbose_name_plural = 'Vehicle Inspections'
        ordering = ['-inspected_at']


class InspectionCheckItem(models.Model):
    """
    One checklist row per category per inspection.
    is_ok=True  → Yes (no issue)
    is_ok=False → No  (has issue — detail required, photos optional)
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection = models.ForeignKey(
        VehicleInspection,
        on_delete=models.CASCADE,
        related_name='check_items'
    )
    category = models.CharField(max_length=30, choices=CheckItemCategory.choices)
    is_ok = models.BooleanField(default=True)
    issue_detail = models.TextField(
        blank=True,
        help_text="Required when is_ok=False."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.category} — {'OK' if self.is_ok else 'ISSUE'}"

    class Meta:
        unique_together = [['inspection', 'category']]
        ordering = ['category']


class InspectionCheckPhoto(models.Model):
    """Photos for a check item. Only relevant when is_ok=False."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    check_item = models.ForeignKey(
        InspectionCheckItem,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    photo = models.ImageField(upload_to='fleet_inspections/photos/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']
