from django.db import models
from django.conf import settings
import uuid


class VehicleStatus(models.TextChoices):
    HEALTHY = 'healthy', 'Healthy'
    ISSUE_REPORTED = 'issue_reported', 'Issue Reported'
    INSPECTION_DUE = 'inspection_due', 'Inspection Due'
    SERVICE_OVERDUE = 'service_overdue', 'Service Overdue'


class MaintenanceStatus(models.TextChoices):
    SCHEDULED = 'scheduled', 'Scheduled'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class Vehicle(models.Model):
    """
    A company vehicle in the fleet.

    Status logic (computed via update_status() method):
    - HEALTHY:          No open issues, inspection done within 7 days, not service overdue.
    - INSPECTION_DUE:   Last inspection was more than 7 days ago (or never inspected).
    - ISSUE_REPORTED:   Any linked VehicleInspection has an open issue flag.
    - SERVICE_OVERDUE:  current_odometer_km >= next_service_km (if both are set).

    Priority order when multiple conditions are true:
    ISSUE_REPORTED > SERVICE_OVERDUE > INSPECTION_DUE > HEALTHY
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=150, help_text="e.g. Van 04, Ute 02")
    plate = models.CharField(
        max_length=20,
        unique=True,
        help_text="Vehicle number plate e.g. ABC-1234"
    )
    picture = models.ImageField(
        upload_to='fleet/vehicles/',
        null=True,
        blank=True
    )

    # Status is stored and updated via update_status() — not set manually by admin
    status = models.CharField(
        max_length=20,
        choices=VehicleStatus.choices,
        default=VehicleStatus.HEALTHY
    )

    # Service tracking
    current_odometer_km = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Current odometer reading in km"
    )
    next_service_km = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Odometer reading (km) at which next service is due"
    )

    # Assignment — one employee at a time, optional
    # assigned_to = models.ForeignKey(
    #     settings.AUTH_USER_MODEL,
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name='assigned_vehicles',
    #     limit_choices_to={'is_staff': False, 'is_superuser': False},
    #     help_text="Employee currently assigned to this vehicle"
    # )

    # Additional info
    make = models.CharField(max_length=100, blank=True, help_text="e.g. Toyota")
    model_name = models.CharField(max_length=100, blank=True, help_text="e.g. HiAce")
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.plate})"

    # ------------------------------------------------------------------
    # Status logic — called after each inspection save or odometer update
    # ------------------------------------------------------------------
    def update_status(self):
        """
        Recomputes and saves vehicle status based on:
        1. Open issues from latest inspection
        2. Odometer vs next service km
        3. Days since last inspection
        Highest priority condition wins.
        """
        from django.utils import timezone
        from datetime import timedelta

        new_status = VehicleStatus.HEALTHY

        # Only submitted inspections count for history
        submitted = self.inspections.filter(status='submitted')

        # Priority 3 — inspection due
        last = submitted.order_by('-submitted_at').first()
        last_date = last.submitted_at if last else None
        if last_date is None or (timezone.now() - last_date).days > 7:
            new_status = VehicleStatus.INSPECTION_DUE

        # Priority 2 — service overdue
        if (
            self.current_odometer_km is not None and
            self.next_service_km is not None and
            self.current_odometer_km >= self.next_service_km
        ):
            new_status = VehicleStatus.SERVICE_OVERDUE

        # Priority 1 — open issue from any submitted inspection
        if submitted.filter(has_open_issue=True).exists():
            new_status = VehicleStatus.ISSUE_REPORTED

        self.status = new_status
        Vehicle.objects.filter(pk=self.pk).update(status=new_status)

    @property
    def last_inspection_date(self):
        latest = self.inspections.filter(
            status='submitted'
        ).order_by('-submitted_at').first()
        return latest.submitted_at if latest else None

    @property
    def is_service_overdue(self):
        if self.current_odometer_km and self.next_service_km:
            return self.current_odometer_km >= self.next_service_km
        return False

    @property
    def km_until_service(self):
        if self.current_odometer_km and self.next_service_km:
            diff = self.next_service_km - self.current_odometer_km
            return max(diff, 0)
        return None

    class Meta:
        verbose_name = 'Vehicle'
        verbose_name_plural = 'Vehicles'
        ordering = ['name']


class MaintenanceSchedule(models.Model):
    """
    Admin-scheduled maintenance for a vehicle.
    Each vehicle can have multiple scheduled/completed maintenance records.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='maintenance_schedules'
    )
    scheduled_date = models.DateField()
    description = models.TextField(help_text="What maintenance is being performed")
    status = models.CharField(
        max_length=20,
        choices=MaintenanceStatus.choices,
        default=MaintenanceStatus.SCHEDULED
    )
    odometer_at_service = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Odometer reading when service was performed"
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    performed_by = models.CharField(
        max_length=200,
        blank=True,
        help_text="Service center or mechanic name"
    )
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.vehicle.name} — {self.scheduled_date} ({self.status})"

    class Meta:
        verbose_name = 'Maintenance Schedule'
        verbose_name_plural = 'Maintenance Schedules'
        ordering = ['-scheduled_date']