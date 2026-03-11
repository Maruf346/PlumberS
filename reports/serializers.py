from rest_framework import serializers
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from .models import (
    JobReport, ReportPhoto, ReportType,
    RootReportSubmission, ApplianceReportSubmission,
    DrainInspectionSubmission, LeakInspectionSubmission,
    SprayTestSubmission,
    YesNoNA, PassFailNA, ConditionRating,
    DwellingType, RoofType, PropertyConstruction,
    AreaOfInspection, PipeConstruction,
    TestingLocation, SprayTestLocation,
)


# ==================== HELPERS ====================

def _choices_list(choices_class):
    """Return choices as [{'value': ..., 'label': ...}] for frontend dropdowns."""
    return [{'value': c[0], 'label': c[1]} for c in choices_class.choices]


def _build_snapshot(job_report):
    """
    Build a snapshot dict of pre-filled fields from Job/Client/User
    at the time of submission. Stored on the submission model for PDF integrity.
    """
    job = job_report.job
    client = job.client
    employee = job.assigned_to

    return {
        'job_id': job.job_id,
        'job_name': job.job_name,
        'site_address': client.address if client else '',
        'client_name': client.name if client else '',
        'client_phone': client.phone if client else '',
        'client_email': client.email if client else '',
        'contact_person_name': client.contact_person_name if client else '',
        'site_access': client.site_access if client else '',
        'employee_name': employee.full_name if employee else '',
        'employee_phone': str(employee.phone) if employee and employee.phone else '',
        'employee_email': employee.email if employee else '',
        'scheduled_datetime': str(job.scheduled_datetime) if job.scheduled_datetime else '',
    }


# ==================== REPORT PHOTO SERIALIZER ====================

class ReportPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportPhoto
        fields = ['id', 'photo_type', 'image', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


# ==================== JOB REPORT LIST SERIALIZER (admin job panel) ====================

class JobReportListSerializer(serializers.ModelSerializer):
    """Used by admin to see all reports attached to a job."""
    report_type_display = serializers.CharField(source='get_report_type_display', read_only=True)
    submitted_by_name = serializers.CharField(
        source='submitted_by.full_name', read_only=True, allow_null=True
    )

    class Meta:
        model = JobReport
        fields = [
            'id', 'report_type', 'report_type_display',
            'is_submitted', 'submitted_by', 'submitted_by_name',
            'submitted_at', 'created_at',
        ]
        read_only_fields = fields


# ==================== REPORT TYPES ENDPOINT SERIALIZER ====================

class ReportTypeChoiceSerializer(serializers.Serializer):
    """Returns available report type choices for admin job creation form."""
    value = serializers.CharField()
    label = serializers.CharField()


# ==================== BASE FORM SERIALIZER ====================

class BaseFormSerializer(serializers.Serializer):
    """
    Common pre-filled fields returned on every form GET.
    These come from the DB — employee cannot edit them.
    """
    job_id = serializers.CharField()
    job_name = serializers.CharField()
    site_address = serializers.CharField()
    client_name = serializers.CharField()
    client_phone = serializers.CharField()
    client_email = serializers.CharField()
    contact_person_name = serializers.CharField()
    employee_name = serializers.CharField()
    scheduled_datetime = serializers.CharField()
    is_submitted = serializers.BooleanField()


# ==================== ROOT REPORT ====================

class RootReportFormSerializer(serializers.Serializer):
    """
    GET /api/reports/{job_report_id}/form/
    Returns pre-filled data + available choices for the Root Report form.
    """
    pre_filled = serializers.SerializerMethodField()
    choices = serializers.SerializerMethodField()
    submission = serializers.SerializerMethodField()

    def get_pre_filled(self, obj):
        job = obj.job
        client = job.client
        employee = job.assigned_to
        return {
            'job_id': job.job_id,
            'job_name': job.job_name,
            'site_address': client.address if client else '',
            'builder': client.name if client else '',
            'insured_details': {
                'name': client.name if client else '',
                'phone': client.phone if client else '',
                'email': client.email if client else '',
                'contact_person': client.contact_person_name if client else '',
                'address': client.address if client else '',
            },
            'inspection_conducted_by': employee.full_name if employee else '',
        }

    def get_choices(self, obj):
        return {
            'type_of_dwelling': _choices_list(DwellingType),
            'type_of_roof': _choices_list(RoofType),
            'leak_fixed_by_insured': _choices_list(YesNoNA),
            'leak_present': _choices_list(YesNoNA),
            'cause_of_leak_found': _choices_list(YesNoNA),
            'leak_fixed': _choices_list(YesNoNA),
        }

    def get_submission(self, obj):
        if not obj.is_submitted:
            return None
        try:
            return RootReportReadSerializer(obj.root_submission).data
        except RootReportSubmission.DoesNotExist:
            return None


class RootReportSubmitSerializer(serializers.ModelSerializer):
    """
    POST /api/reports/{job_report_id}/submit/
    Accepts only employee-filled fields.
    Pre-filled fields are auto-populated from DB via snapshot.
    """
    # Photo fields — accept multiple uploaded files
    front_of_dwelling = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    damage_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    job_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )

    class Meta:
        model = RootReportSubmission
        fields = [
            'attendance_datetime',
            'discussion_with_insured',
            'type_of_dwelling',
            'front_of_dwelling',
            'resulting_damages',
            'damage_photos',
            'leak_fixed_by_insured',
            'type_of_roof',
            'pitch_of_roof',
            'leak_present',
            'cause_of_leak_found',
            'leak_fixed',
            'works_required',
            'conclusion',
            'job_photos',
        ]

    def validate(self, data):
        # Ensure not already submitted
        job_report = self.context['job_report']
        if job_report.is_submitted:
            raise serializers.ValidationError('This report has already been submitted.')
        return data

    def create(self, validated_data):
        front_photos = validated_data.pop('front_of_dwelling', [])
        damage_photos = validated_data.pop('damage_photos', [])
        job_photos = validated_data.pop('job_photos', [])

        job_report = self.context['job_report']
        user = self.context['request'].user

        submission = RootReportSubmission.objects.create(
            job_report=job_report,
            submitted_by=user,
            snapshot=_build_snapshot(job_report),
            **validated_data
        )

        ct = ContentType.objects.get_for_model(RootReportSubmission)
        self._save_photos(ct, submission.id, front_photos, 'front_of_dwelling')
        self._save_photos(ct, submission.id, damage_photos, 'damage_photo')
        self._save_photos(ct, submission.id, job_photos, 'job_photo')

        # Mark JobReport as submitted
        job_report.is_submitted = True
        job_report.submitted_by = user
        job_report.submitted_at = timezone.now()
        job_report.save()

        return submission

    @staticmethod
    def _save_photos(content_type, object_id, photos, photo_type):
        for photo in photos:
            ReportPhoto.objects.create(
                content_type=content_type,
                object_id=object_id,
                photo_type=photo_type,
                image=photo
            )


class RootReportReadSerializer(serializers.ModelSerializer):
    """Read-only view of a submitted Root Report."""
    photos = serializers.SerializerMethodField()
    submitted_by_name = serializers.CharField(source='submitted_by.full_name', read_only=True)

    class Meta:
        model = RootReportSubmission
        fields = [
            'id', 'submitted_by', 'submitted_by_name',
            'snapshot', 'attendance_datetime',
            'discussion_with_insured', 'type_of_dwelling',
            'resulting_damages', 'leak_fixed_by_insured',
            'type_of_roof', 'pitch_of_roof',
            'leak_present', 'cause_of_leak_found', 'leak_fixed',
            'works_required', 'conclusion',
            'photos', 'created_at',
        ]
        read_only_fields = fields

    def get_photos(self, obj):
        ct = ContentType.objects.get_for_model(RootReportSubmission)
        photos = ReportPhoto.objects.filter(content_type=ct, object_id=obj.id)
        request = self.context.get('request')
        result = {}
        for photo in photos:
            pt = photo.photo_type
            url = request.build_absolute_uri(photo.image.url) if request and photo.image else None
            result.setdefault(pt, []).append({
                'id': str(photo.id),
                'url': url,
                'uploaded_at': photo.uploaded_at,
            })
        return result


# ==================== APPLIANCE REPORT ====================

class ApplianceReportFormSerializer(serializers.Serializer):
    pre_filled = serializers.SerializerMethodField()
    choices = serializers.SerializerMethodField()
    submission = serializers.SerializerMethodField()

    def get_pre_filled(self, obj):
        job = obj.job
        client = job.client
        employee = job.assigned_to
        return {
            'site_address': client.address if client else '',
            'builder': client.name if client else '',
            'insured_details': {
                'name': client.name if client else '',
                'phone': client.phone if client else '',
                'email': client.email if client else '',
                'contact_person': client.contact_person_name if client else '',
                'address': client.address if client else '',
            },
            'inspection_conducted_by': employee.full_name if employee else '',
        }

    def get_choices(self, obj):
        return {}   # No choice fields in Appliance Report

    def get_submission(self, obj):
        if not obj.is_submitted:
            return None
        try:
            return ApplianceReportReadSerializer(obj.appliance_submission).data
        except ApplianceReportSubmission.DoesNotExist:
            return None


class ApplianceReportSubmitSerializer(serializers.ModelSerializer):
    front_of_property = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    job_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )

    class Meta:
        model = ApplianceReportSubmission
        fields = [
            'attendance_datetime',
            'front_of_property',
            'discussion_with_insured',
            'appliance_brand', 'model_no', 'approx_age',
            'conclusion',
            'job_photos',
        ]

    def validate(self, data):
        if self.context['job_report'].is_submitted:
            raise serializers.ValidationError('This report has already been submitted.')
        return data

    def create(self, validated_data):
        front_photos = validated_data.pop('front_of_property', [])
        job_photos = validated_data.pop('job_photos', [])
        job_report = self.context['job_report']
        user = self.context['request'].user

        submission = ApplianceReportSubmission.objects.create(
            job_report=job_report,
            submitted_by=user,
            snapshot=_build_snapshot(job_report),
            **validated_data
        )
        ct = ContentType.objects.get_for_model(ApplianceReportSubmission)
        RootReportSubmitSerializer._save_photos(ct, submission.id, front_photos, 'front_of_property')
        RootReportSubmitSerializer._save_photos(ct, submission.id, job_photos, 'job_photo')

        job_report.is_submitted = True
        job_report.submitted_by = user
        job_report.submitted_at = timezone.now()
        job_report.save()
        return submission


class ApplianceReportReadSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    submitted_by_name = serializers.CharField(source='submitted_by.full_name', read_only=True)

    class Meta:
        model = ApplianceReportSubmission
        fields = [
            'id', 'submitted_by', 'submitted_by_name',
            'snapshot', 'attendance_datetime',
            'discussion_with_insured',
            'appliance_brand', 'model_no', 'approx_age',
            'conclusion', 'photos', 'created_at',
        ]
        read_only_fields = fields

    def get_photos(self, obj):
        ct = ContentType.objects.get_for_model(ApplianceReportSubmission)
        photos = ReportPhoto.objects.filter(content_type=ct, object_id=obj.id)
        request = self.context.get('request')
        result = {}
        for photo in photos:
            url = request.build_absolute_uri(photo.image.url) if request and photo.image else None
            result.setdefault(photo.photo_type, []).append({'id': str(photo.id), 'url': url})
        return result


# ==================== DRAIN INSPECTION REPORT ====================

class DrainInspectionFormSerializer(serializers.Serializer):
    pre_filled = serializers.SerializerMethodField()
    choices = serializers.SerializerMethodField()
    submission = serializers.SerializerMethodField()

    def get_pre_filled(self, obj):
        job = obj.job
        client = job.client
        employee = job.assigned_to
        return {
            'job_id': job.job_id,
            'site_address': client.address if client else '',
            'client_name': client.name if client else '',
            'site_contact_details': {
                'name': client.name if client else '',
                'phone': client.phone if client else '',
                'email': client.email if client else '',
                'contact_person': client.contact_person_name if client else '',
            },
            'person_undertaking_investigation': employee.full_name if employee else '',
        }

    def get_choices(self, obj):
        return {
            'property_construction': _choices_list(PropertyConstruction),
            'area_of_inspection': _choices_list(AreaOfInspection),
            'pipe_construction': _choices_list(PipeConstruction),
        }

    def get_submission(self, obj):
        if not obj.is_submitted:
            return None
        try:
            return DrainInspectionReadSerializer(obj.drain_submission).data
        except DrainInspectionSubmission.DoesNotExist:
            return None


class DrainInspectionSubmitSerializer(serializers.ModelSerializer):
    front_of_dwelling = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    damage_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    job_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )

    class Meta:
        model = DrainInspectionSubmission
        fields = [
            'attendance_datetime',
            'front_of_dwelling',
            'property_construction',
            'discussion_with_insured',
            'resultant_damage',
            'damage_photos',
            'area_of_inspection',
            'pipe_construction',
            'conclusion',
            'job_photos',
        ]

    def validate(self, data):
        if self.context['job_report'].is_submitted:
            raise serializers.ValidationError('This report has already been submitted.')
        return data

    def create(self, validated_data):
        front_photos = validated_data.pop('front_of_dwelling', [])
        damage_photos = validated_data.pop('damage_photos', [])
        job_photos = validated_data.pop('job_photos', [])
        job_report = self.context['job_report']
        user = self.context['request'].user

        submission = DrainInspectionSubmission.objects.create(
            job_report=job_report,
            submitted_by=user,
            snapshot=_build_snapshot(job_report),
            **validated_data
        )
        ct = ContentType.objects.get_for_model(DrainInspectionSubmission)
        RootReportSubmitSerializer._save_photos(ct, submission.id, front_photos, 'front_of_dwelling')
        RootReportSubmitSerializer._save_photos(ct, submission.id, damage_photos, 'damage_photo')
        RootReportSubmitSerializer._save_photos(ct, submission.id, job_photos, 'job_photo')

        job_report.is_submitted = True
        job_report.submitted_by = user
        job_report.submitted_at = timezone.now()
        job_report.save()
        return submission


class DrainInspectionReadSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    submitted_by_name = serializers.CharField(source='submitted_by.full_name', read_only=True)

    class Meta:
        model = DrainInspectionSubmission
        fields = [
            'id', 'submitted_by', 'submitted_by_name',
            'snapshot', 'attendance_datetime',
            'property_construction', 'discussion_with_insured',
            'resultant_damage', 'area_of_inspection',
            'pipe_construction', 'conclusion',
            'photos', 'created_at',
        ]
        read_only_fields = fields

    def get_photos(self, obj):
        ct = ContentType.objects.get_for_model(DrainInspectionSubmission)
        photos = ReportPhoto.objects.filter(content_type=ct, object_id=obj.id)
        request = self.context.get('request')
        result = {}
        for photo in photos:
            url = request.build_absolute_uri(photo.image.url) if request and photo.image else None
            result.setdefault(photo.photo_type, []).append({'id': str(photo.id), 'url': url})
        return result


# ==================== LEAK INSPECTION REPORT ====================

class LeakInspectionFormSerializer(serializers.Serializer):
    pre_filled = serializers.SerializerMethodField()
    choices = serializers.SerializerMethodField()
    submission = serializers.SerializerMethodField()

    def get_pre_filled(self, obj):
        job = obj.job
        client = job.client
        employee = job.assigned_to
        return {
            'job_id': job.job_id,
            'site_address': client.address if client else '',
            'client_name': client.name if client else '',
            'site_contact_details': {
                'name': client.name if client else '',
                'phone': client.phone if client else '',
                'email': client.email if client else '',
                'contact_person': client.contact_person_name if client else '',
            },
            'person_undertaking_investigation': employee.full_name if employee else '',
        }

    def get_choices(self, obj):
        return {
            'property_construction': _choices_list(PropertyConstruction),
            'testing_location': _choices_list(TestingLocation),
            'pressure_tests': _choices_list(PassFailNA),
            'flood_spray_tests': _choices_list(PassFailNA),
            'condition_ratings': _choices_list(ConditionRating),
        }

    def get_submission(self, obj):
        if not obj.is_submitted:
            return None
        try:
            return LeakInspectionReadSerializer(obj.leak_submission).data
        except LeakInspectionSubmission.DoesNotExist:
            return None


class LeakInspectionSubmitSerializer(serializers.ModelSerializer):
    front_of_dwelling = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    damage_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    whole_area_photo = serializers.ImageField(write_only=True, required=False)
    test_results_photo = serializers.ImageField(write_only=True, required=False)
    spindle_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    job_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )

    class Meta:
        model = LeakInspectionSubmission
        fields = [
            'attendance_datetime',
            'front_of_dwelling',
            'property_construction',
            'discussion_with_site_contact',
            'resultant_damage',
            'damage_photos',
            'testing_location',
            'whole_area_photo',
            'pressure_cold_line', 'pressure_hot_line',
            'pressure_shower_breech', 'pressure_bath_breech',
            'test_results_photo',
            'flood_test_shower', 'flood_test_bath',
            'spray_test_wall_tiles', 'spray_test_shower_screen',
            'tile_condition', 'grout_condition', 'silicone_condition',
            'silicone_around_spindles',
            'spindle_photos',
            'conclusion',
            'job_photos',
        ]

    def validate(self, data):
        if self.context['job_report'].is_submitted:
            raise serializers.ValidationError('This report has already been submitted.')
        return data

    def create(self, validated_data):
        front_photos = validated_data.pop('front_of_dwelling', [])
        damage_photos = validated_data.pop('damage_photos', [])
        whole_area_photo = validated_data.pop('whole_area_photo', None)
        test_results_photo = validated_data.pop('test_results_photo', None)
        spindle_photos = validated_data.pop('spindle_photos', [])
        job_photos = validated_data.pop('job_photos', [])

        job_report = self.context['job_report']
        user = self.context['request'].user

        submission = LeakInspectionSubmission.objects.create(
            job_report=job_report,
            submitted_by=user,
            snapshot=_build_snapshot(job_report),
            **validated_data
        )
        ct = ContentType.objects.get_for_model(LeakInspectionSubmission)
        save = RootReportSubmitSerializer._save_photos
        save(ct, submission.id, front_photos, 'front_of_dwelling')
        save(ct, submission.id, damage_photos, 'damage_photo')
        save(ct, submission.id, spindle_photos, 'spindle_photo')
        save(ct, submission.id, job_photos, 'job_photo')
        if whole_area_photo:
            save(ct, submission.id, [whole_area_photo], 'whole_area')
        if test_results_photo:
            save(ct, submission.id, [test_results_photo], 'test_results')

        job_report.is_submitted = True
        job_report.submitted_by = user
        job_report.submitted_at = timezone.now()
        job_report.save()
        return submission


class LeakInspectionReadSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    submitted_by_name = serializers.CharField(source='submitted_by.full_name', read_only=True)

    class Meta:
        model = LeakInspectionSubmission
        fields = [
            'id', 'submitted_by', 'submitted_by_name', 'snapshot',
            'attendance_datetime', 'property_construction',
            'discussion_with_site_contact', 'resultant_damage',
            'testing_location',
            'pressure_cold_line', 'pressure_hot_line',
            'pressure_shower_breech', 'pressure_bath_breech',
            'flood_test_shower', 'flood_test_bath',
            'spray_test_wall_tiles', 'spray_test_shower_screen',
            'tile_condition', 'grout_condition', 'silicone_condition',
            'silicone_around_spindles',
            'conclusion', 'photos', 'created_at',
        ]
        read_only_fields = fields

    def get_photos(self, obj):
        ct = ContentType.objects.get_for_model(LeakInspectionSubmission)
        photos = ReportPhoto.objects.filter(content_type=ct, object_id=obj.id)
        request = self.context.get('request')
        result = {}
        for photo in photos:
            url = request.build_absolute_uri(photo.image.url) if request and photo.image else None
            result.setdefault(photo.photo_type, []).append({'id': str(photo.id), 'url': url})
        return result


# ==================== SPRAY TEST REPORT ====================

class SprayTestFormSerializer(serializers.Serializer):
    pre_filled = serializers.SerializerMethodField()
    choices = serializers.SerializerMethodField()
    submission = serializers.SerializerMethodField()

    def get_pre_filled(self, obj):
        job = obj.job
        client = job.client
        employee = job.assigned_to
        return {
            'job_id': job.job_id,
            'site_address': client.address if client else '',
            'client_name': client.name if client else '',
            'site_contact_details': {
                'name': client.name if client else '',
                'phone': client.phone if client else '',
                'email': client.email if client else '',
                'contact_person': client.contact_person_name if client else '',
            },
            'person_undertaking_investigation': employee.full_name if employee else '',
        }

    def get_choices(self, obj):
        return {
            'property_construction': _choices_list(PropertyConstruction),
            'testing_location': _choices_list(SprayTestLocation),
            'pass_fail_na': _choices_list(PassFailNA),
            'condition_ratings': _choices_list(ConditionRating),
        }

    def get_submission(self, obj):
        if not obj.is_submitted:
            return None
        try:
            return SprayTestReadSerializer(obj.spray_submission).data
        except SprayTestSubmission.DoesNotExist:
            return None


class SprayTestSubmitSerializer(serializers.ModelSerializer):
    front_of_dwelling = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    damage_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )
    whole_area_photo = serializers.ImageField(write_only=True, required=False)
    job_photos = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=False
    )

    class Meta:
        model = SprayTestSubmission
        fields = [
            'attendance_datetime',
            'front_of_dwelling',
            'property_construction',
            'discussion_with_insured',
            'resultant_damage',
            'damage_photos',
            'testing_location',
            'whole_area_photo',
            'flood_test', 'flood_test_notes',
            'spray_test', 'spray_test_notes',
            'tile_condition', 'tile_condition_notes',
            'grout_condition', 'grout_condition_notes',
            'silicone_condition', 'silicone_condition_notes',
            'conclusion',
            'job_photos',
        ]

    def validate(self, data):
        if self.context['job_report'].is_submitted:
            raise serializers.ValidationError('This report has already been submitted.')
        return data

    def create(self, validated_data):
        front_photos = validated_data.pop('front_of_dwelling', [])
        damage_photos = validated_data.pop('damage_photos', [])
        whole_area_photo = validated_data.pop('whole_area_photo', None)
        job_photos = validated_data.pop('job_photos', [])

        job_report = self.context['job_report']
        user = self.context['request'].user

        submission = SprayTestSubmission.objects.create(
            job_report=job_report,
            submitted_by=user,
            snapshot=_build_snapshot(job_report),
            **validated_data
        )
        ct = ContentType.objects.get_for_model(SprayTestSubmission)
        save = RootReportSubmitSerializer._save_photos
        save(ct, submission.id, front_photos, 'front_of_dwelling')
        save(ct, submission.id, damage_photos, 'damage_photo')
        save(ct, submission.id, job_photos, 'job_photo')
        if whole_area_photo:
            save(ct, submission.id, [whole_area_photo], 'whole_area')

        job_report.is_submitted = True
        job_report.submitted_by = user
        job_report.submitted_at = timezone.now()
        job_report.save()
        return submission


class SprayTestReadSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    submitted_by_name = serializers.CharField(source='submitted_by.full_name', read_only=True)

    class Meta:
        model = SprayTestSubmission
        fields = [
            'id', 'submitted_by', 'submitted_by_name', 'snapshot',
            'attendance_datetime', 'property_construction',
            'discussion_with_insured', 'resultant_damage',
            'testing_location',
            'flood_test', 'flood_test_notes',
            'spray_test', 'spray_test_notes',
            'tile_condition', 'tile_condition_notes',
            'grout_condition', 'grout_condition_notes',
            'silicone_condition', 'silicone_condition_notes',
            'conclusion', 'photos', 'created_at',
        ]
        read_only_fields = fields

    def get_photos(self, obj):
        ct = ContentType.objects.get_for_model(SprayTestSubmission)
        photos = ReportPhoto.objects.filter(content_type=ct, object_id=obj.id)
        request = self.context.get('request')
        result = {}
        for photo in photos:
            url = request.build_absolute_uri(photo.image.url) if request and photo.image else None
            result.setdefault(photo.photo_type, []).append({'id': str(photo.id), 'url': url})
        return result
