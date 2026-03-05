from django.db import models
from django.conf import settings
import uuid


class InspectionStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SUBMITTED = 'submitted', 'Submitted'


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
    A single inspection session for a vehicle.

    - Created as DRAFT when employee starts/resumes.
    - Moved to SUBMITTED when employee hits Submit Inspection.
    - Only one active DRAFT per vehicle per employee at a time.
    - Employee must have an active job (PENDING or IN_PROGRESS)
      with this vehicle assigned — enforced in the view.

    has_open_issue is set to True on submit if any check item
    has is_ok=False. This plugs directly into Vehicle.update_status().
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
    status = models.CharField(
        max_length=10,
        choices=InspectionStatus.choices,
        default=InspectionStatus.DRAFT
    )
    has_open_issue = models.BooleanField(
        default=False,
        help_text="True if any check item has is_ok=False on submission."
    )
    notes = models.TextField(
        blank=True,
        help_text="Overall inspection notes."
    )

    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vehicle.name} — {self.status} — {self.inspected_by}"

    @property
    def inspected_at(self):
        """
        Used by Vehicle.update_status() and history views.
        Returns submitted_at if submitted, otherwise started_at.
        """
        return self.submitted_at or self.started_at

    @property
    def completed_items_count(self):
        return self.check_items.count()

    @property
    def issue_count(self):
        return self.check_items.filter(is_ok=False).count()

    class Meta:
        verbose_name = 'Vehicle Inspection'
        verbose_name_plural = 'Vehicle Inspections'
        ordering = ['-started_at']


class InspectionCheckItem(models.Model):
    """
    One checklist row per category per inspection.
    is_ok=True  → Yes (no issue, all good)
    is_ok=False → No  (has issue — detail and photos required)

    Only one record per category per inspection is allowed.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection = models.ForeignKey(
        VehicleInspection,
        on_delete=models.CASCADE,
        related_name='check_items'
    )
    category = models.CharField(
        max_length=30,
        choices=CheckItemCategory.choices
    )
    is_ok = models.BooleanField(
        default=True,
        help_text="True = no issue (Yes). False = has issue (No)."
    )
    issue_detail = models.TextField(
        blank=True,
        help_text="Required when is_ok=False. Describe the issue."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        status = "OK" if self.is_ok else "ISSUE"
        return f"{self.inspection.vehicle.name} — {self.category} — {status}"

    class Meta:
        verbose_name = 'Inspection Check Item'
        verbose_name_plural = 'Inspection Check Items'
        # One row per category per inspection
        unique_together = [['inspection', 'category']]
        ordering = ['category']


class InspectionCheckPhoto(models.Model):
    """
    Photos linked to a specific InspectionCheckItem.
    Unlimited per item — only relevant when is_ok=False.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    check_item = models.ForeignKey(
        InspectionCheckItem,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    photo = models.ImageField(upload_to='fleet_inspections/photos/')
    caption = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.check_item}"

    class Meta:
        verbose_name = 'Inspection Check Photo'
        verbose_name_plural = 'Inspection Check Photos'
        ordering = ['uploaded_at']