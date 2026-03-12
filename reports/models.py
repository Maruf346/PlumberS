from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
import uuid


# ==================== CHOICES ====================

class ReportType(models.TextChoices):
    ROOF = 'roof', 'Roof Report'
    APPLIANCE = 'appliance', 'Appliance Report'
    DRAIN_INSPECTION = 'drain_inspection', 'Drain Inspection Report'
    LEAK_INSPECTION = 'leak_inspection', 'Leak Inspection Report'
    SPRAY_TEST = 'spray_test', 'Spray Test Report'


class YesNoNA(models.TextChoices):
    YES = 'yes', 'Yes'
    NO = 'no', 'No'
    NA = 'na', 'N/A'


class PassFailNA(models.TextChoices):
    PASSED = 'passed', 'Passed'
    FAILED = 'failed', 'Failed'
    NA = 'na', 'N/A'


class ConditionRating(models.TextChoices):
    EXCELLENT = 'excellent', 'Excellent'
    GOOD = 'good', 'Good'
    AVERAGE = 'average', 'Average'
    POOR = 'poor', 'Poor'
    VERY_POOR = 'very_poor', 'Very Poor'


class DwellingType(models.TextChoices):
    SINGLE_STORY = 'single_story', 'Single Story'
    TWO_STORY = 'two_story', 'Two Story'
    COMPLEX = 'complex', 'Complex Building'


class RoofType(models.TextChoices):
    IRON = 'iron', 'Iron'
    TILE = 'tile', 'Tile'
    ASBESTOS = 'asbestos', 'Asbestos'
    POLY_SHEETING = 'poly_sheeting', 'Poly Sheeting'
    PRESSED_METAL = 'pressed_metal', 'Pressed Metal'


class PropertyConstruction(models.TextChoices):
    BRICK_VENEER = 'brick_veneer', 'Brick Veneer'
    DOUBLE_BRICK = 'double_brick', 'Double Brick'


class AreaOfInspection(models.TextChoices):
    CONSUMER_SEWER = 'consumer_sewer', 'Consumer Sewer'
    CONSUMER_STORMWATER = 'consumer_stormwater', 'Consumer Stormwater'


class PipeConstruction(models.TextChoices):
    PVC = 'pvc', 'PVC'
    CERAMIC = 'ceramic', 'Ceramic'
    HDPE = 'hdpe', 'HDPE'
    GALVANISED = 'galvanised', 'Galvanised'
    LEAD = 'lead', 'Lead'


class TestingLocation(models.TextChoices):
    BATHROOM = 'bathroom', 'Bathroom'
    ENSUITE = 'ensuite', 'Ensuite'
    KITCHEN = 'kitchen', 'Kitchen'
    LAUNDRY = 'laundry', 'Laundry'
    OTHER = 'other', 'Other'


class SprayTestLocation(models.TextChoices):
    BATHROOM = 'bathroom', 'Bathroom'
    ENSUITE = 'ensuite', 'Ensuite'
    KITCHEN = 'kitchen', 'Kitchen'
    LAUNDRY = 'laundry', 'Laundry'
    EXTERNAL_WALL = 'external_wall', 'External Wall'
    BALCONY = 'balcony', 'Balcony'
    WINDOW = 'window', 'Window'
    DOOR = 'door', 'Door'
    ROLLER_DOOR = 'roller_door', 'Roller Door'
    OTHER = 'other', 'Other'


# ==================== JOB REPORT (LINKING TABLE) ====================

class JobReport(models.Model):
    """
    Links a Job to a ReportType.
    One record per report type per job.
    Created at job creation time by admin.
    Tracks submission status.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        'jobs.Job',
        on_delete=models.CASCADE,
        related_name='job_reports'
    )
    report_type = models.CharField(
        max_length=30,
        choices=ReportType.choices
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_reports',
        help_text="Admin who attached this report type to the job"
    )
    is_submitted = models.BooleanField(default=False)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submitted_reports'
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'report_type')
        ordering = ['created_at']
        verbose_name = 'Job Report'
        verbose_name_plural = 'Job Reports'

    def __str__(self):
        return f"{self.job.job_id} — {self.get_report_type_display()}"


# ==================== REPORT PHOTO (SHARED) ====================

def report_photo_path(instance, filename):
    return f'reports/{instance.photo_type}/{filename}'


class ReportPhoto(models.Model):
    """
    Generic photo model shared across all report submission types.
    Uses GenericForeignKey to point to any submission model.
    photo_type identifies what the photo represents within the report.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Generic FK — points to any submission model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey('content_type', 'object_id')

    photo_type = models.CharField(
        max_length=50,
        help_text=(
            "What this photo represents. Examples: "
            "'front_of_dwelling', 'damage_photo', 'job_photo', "
            "'test_results', 'spindle_photo', 'whole_area'"
        )
    )
    image = models.ImageField(upload_to=report_photo_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.photo_type} — {self.object_id}"


# ==================== ROOF REPORT ====================

class RoofReportSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_report = models.OneToOneField(
        JobReport,
        on_delete=models.CASCADE,
        related_name='roof_submission'
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='roof_reports'
    )

    # Snapshot of pre-filled DB fields at submission time (for PDF integrity)
    snapshot = models.JSONField(
        default=dict,
        help_text="Snapshot of job/client/employee data at submission time"
    )

    # Employee-filled fields
    attendance_datetime = models.DateTimeField(
        help_text="Date and time of attendance on site"
    )
    discussion_with_insured = models.TextField(blank=True)
    type_of_dwelling = models.CharField(
        max_length=20,
        choices=DwellingType.choices,
        blank=True
    )
    # front_of_dwelling → ReportPhoto with photo_type='front_of_dwelling'

    resulting_damages = models.TextField(blank=True)
    # damage_photos → ReportPhoto with photo_type='damage_photo'

    leak_fixed_by_insured = models.CharField(
        max_length=5,
        choices=YesNoNA.choices,
        blank=True
    )
    type_of_roof = models.CharField(
        max_length=15,
        choices=RoofType.choices,
        blank=True
    )
    pitch_of_roof = models.TextField(blank=True)
    leak_present = models.CharField(
        max_length=5,
        choices=YesNoNA.choices,
        blank=True
    )
    cause_of_leak_found = models.CharField(
        max_length=5,
        choices=YesNoNA.choices,
        blank=True
    )
    leak_fixed = models.CharField(
        max_length=5,
        choices=YesNoNA.choices,
        blank=True
    )
    works_required = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)
    # job_photos → ReportPhoto with photo_type='job_photo'

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Roof Report Submission'

    def __str__(self):
        return f"Roof Report — {self.job_report.job.job_id}"


# ==================== APPLIANCE REPORT ====================

class ApplianceReportSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_report = models.OneToOneField(
        JobReport,
        on_delete=models.CASCADE,
        related_name='appliance_submission'
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='appliance_reports'
    )

    snapshot = models.JSONField(default=dict)

    attendance_datetime = models.DateTimeField()
    # front_of_property → ReportPhoto with photo_type='front_of_property'

    discussion_with_insured = models.TextField(blank=True)
    appliance_brand = models.CharField(max_length=150, blank=True)
    model_no = models.CharField(max_length=150, blank=True)
    approx_age = models.CharField(
        max_length=50,
        blank=True,
        help_text="Approximate age of appliance e.g. '5 years', '~10 yrs'"
    )
    conclusion = models.TextField(blank=True)
    # job_photos → ReportPhoto with photo_type='job_photo'

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Appliance Report Submission'

    def __str__(self):
        return f"Appliance Report — {self.job_report.job.job_id}"


# ==================== DRAIN INSPECTION REPORT ====================

class DrainInspectionSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_report = models.OneToOneField(
        JobReport,
        on_delete=models.CASCADE,
        related_name='drain_submission'
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='drain_reports'
    )

    snapshot = models.JSONField(default=dict)

    attendance_datetime = models.DateTimeField()
    # front_of_dwelling → ReportPhoto with photo_type='front_of_dwelling'

    property_construction = models.CharField(
        max_length=20,
        choices=PropertyConstruction.choices,
        blank=True
    )
    discussion_with_insured = models.TextField(blank=True)
    resultant_damage = models.TextField(blank=True)
    # damage_photos → ReportPhoto with photo_type='damage_photo' (multiple)

    area_of_inspection = models.CharField(
        max_length=25,
        choices=AreaOfInspection.choices,
        blank=True
    )
    pipe_construction = models.CharField(
        max_length=15,
        choices=PipeConstruction.choices,
        blank=True
    )
    conclusion = models.TextField(blank=True)
    # job_photos → ReportPhoto with photo_type='job_photo'

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Drain Inspection Submission'

    def __str__(self):
        return f"Drain Inspection — {self.job_report.job.job_id}"


# ==================== LEAK INSPECTION REPORT ====================

class LeakInspectionSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_report = models.OneToOneField(
        JobReport,
        on_delete=models.CASCADE,
        related_name='leak_submission'
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='leak_reports'
    )

    snapshot = models.JSONField(default=dict)

    attendance_datetime = models.DateTimeField()
    # front_of_dwelling → ReportPhoto with photo_type='front_of_dwelling'

    property_construction = models.CharField(
        max_length=20,
        choices=PropertyConstruction.choices,
        blank=True
    )
    discussion_with_site_contact = models.TextField(blank=True)
    resultant_damage = models.TextField(blank=True)
    # damage_photos → ReportPhoto with photo_type='damage_photo' (multiple)

    testing_location = models.CharField(
        max_length=15,
        choices=TestingLocation.choices,
        blank=True
    )
    # whole_area_photo → ReportPhoto with photo_type='whole_area' (single)

    pressure_cold_line = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)
    pressure_hot_line = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)
    pressure_shower_breech = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)
    pressure_bath_breech = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)
    # test_results_photo → ReportPhoto with photo_type='test_results' (single)

    flood_test_shower = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)
    flood_test_bath = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)
    spray_test_wall_tiles = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)
    spray_test_shower_screen = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)

    tile_condition = models.CharField(max_length=10, choices=ConditionRating.choices, blank=True)
    grout_condition = models.CharField(max_length=10, choices=ConditionRating.choices, blank=True)
    silicone_condition = models.CharField(max_length=10, choices=ConditionRating.choices, blank=True)
    silicone_around_spindles = models.BooleanField(
        null=True,
        blank=True,
        help_text="Silicone around spindles and penetrations present?"
    )
    # spindle_photos → ReportPhoto with photo_type='spindle_photo' (multiple)

    conclusion = models.TextField(blank=True)
    # job_photos → ReportPhoto with photo_type='job_photo'

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Leak Inspection Submission'

    def __str__(self):
        return f"Leak Inspection — {self.job_report.job.job_id}"


# ==================== SPRAY TEST REPORT ====================

class SprayTestSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job_report = models.OneToOneField(
        JobReport,
        on_delete=models.CASCADE,
        related_name='spray_submission'
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='spray_reports'
    )

    snapshot = models.JSONField(default=dict)

    attendance_datetime = models.DateTimeField()
    # front_of_dwelling → ReportPhoto with photo_type='front_of_dwelling'

    property_construction = models.CharField(
        max_length=20,
        choices=PropertyConstruction.choices,
        blank=True
    )
    discussion_with_insured = models.TextField(blank=True)
    resultant_damage = models.TextField(blank=True)
    # damage_photos → ReportPhoto with photo_type='damage_photo' (multiple)

    testing_location = models.CharField(
        max_length=15,
        choices=SprayTestLocation.choices,
        blank=True
    )
    # whole_area_photo → ReportPhoto with photo_type='whole_area' (single)

    flood_test = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)
    flood_test_notes = models.TextField(blank=True)

    spray_test = models.CharField(max_length=10, choices=PassFailNA.choices, blank=True)
    spray_test_notes = models.TextField(blank=True)

    tile_condition = models.CharField(max_length=10, choices=ConditionRating.choices, blank=True)
    tile_condition_notes = models.TextField(blank=True)

    grout_condition = models.CharField(max_length=10, choices=ConditionRating.choices, blank=True)
    grout_condition_notes = models.TextField(blank=True)

    silicone_condition = models.CharField(max_length=10, choices=ConditionRating.choices, blank=True)
    silicone_condition_notes = models.TextField(blank=True)

    conclusion = models.TextField(blank=True)
    # job_photos → ReportPhoto with photo_type='job_photo'

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Spray Test Submission'

    def __str__(self):
        return f"Spray Test — {self.job_report.job.job_id}"