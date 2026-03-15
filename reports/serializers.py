from rest_framework import serializers
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from .models import (
    JobReport, ReportPhoto, ReportType,
    RoofReportSubmission, ApplianceReportSubmission,
    DrainInspectionSubmission, LeakInspectionSubmission,
    SprayTestSubmission,
    YesNoNA, PassFailNA, ConditionRating,
    DwellingType, RoofType, PropertyConstruction,
    AreaOfInspection, PipeConstruction,
    TestingLocation, SprayTestLocation,
)


# ==================== HELPERS ====================

def _choices_list(choices_class):
    return [{'value': c[0], 'label': c[1]} for c in choices_class.choices]


def _build_snapshot(job_report):
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


def _field(name, field_type, required=False, choices=None, help_text=''):
    """
    Builds a single field descriptor for the /formfields/ response.

    field_type values the frontend should handle:
        datetime  → date+time picker
        text      → single-line text input
        textarea  → multi-line text input
        select    → dropdown (choices provided)
        boolean   → toggle / checkbox
        photo     → single image upload
        photos    → multiple images upload
    """
    d = {
        'name': name,
        'type': field_type,
        'required': required,
        'help_text': help_text,
    }
    if choices is not None:
        d['choices'] = choices
    if field_type == 'photos':
        d['multiple'] = True
    elif field_type == 'photo':
        d['multiple'] = False
    return d


def _save_photos(content_type, object_id, photos, photo_type):
    for photo in photos:
        ReportPhoto.objects.create(
            content_type=content_type,
            object_id=object_id,
            photo_type=photo_type,
            image=photo
        )


# ==================== SHARED SERIALIZERS ====================

class ReportPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportPhoto
        fields = ['id', 'photo_type', 'image', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class JobReportListSerializer(serializers.ModelSerializer):
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


class ReportTypeChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()


# ==================== ROOF REPORT ====================

class RoofReportFormSerializer(serializers.Serializer):
    """
    GET /form/ — returns pre-filled DB values + choices + submitted data if done.
    Frontend uses this to populate a pre-filled form.
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
            return RoofReportReadSerializer(obj.roof_submission, context=self.context).data
        except RoofReportSubmission.DoesNotExist:
            return None


ROOF_FORM_FIELDS = [
    _field('attendance_datetime', 'datetime', required=True,
           help_text='Date and time of attendance on site'),
    _field('discussion_with_insured', 'textarea',
           help_text='Notes from discussion with insured'),
    _field('type_of_dwelling', 'select', choices=_choices_list(DwellingType),
           help_text='Type of dwelling'),
    _field('front_of_dwelling', 'photos',
           help_text='Photos of the front of the dwelling'),
    _field('resulting_damages', 'textarea',
           help_text='Description of resulting damages'),
    _field('damage_photos', 'photos',
           help_text='Photos showing the resulting damages'),
    _field('leak_fixed_by_insured', 'select', choices=_choices_list(YesNoNA),
           help_text='Was the leak fixed by the insured?'),
    _field('type_of_roof', 'select', choices=_choices_list(RoofType),
           help_text='Type of roof'),
    _field('pitch_of_roof', 'text',
           help_text='Pitch or gradient of the roof'),
    _field('leak_present', 'select', choices=_choices_list(YesNoNA),
           help_text='Is a leak present?'),
    _field('cause_of_leak_found', 'select', choices=_choices_list(YesNoNA),
           help_text='Was the cause of the leak found?'),
    _field('leak_fixed', 'select', choices=_choices_list(YesNoNA),
           help_text='Has the leak been fixed?'),
    _field('works_required', 'textarea',
           help_text='Works required to fix the leak'),
    _field('conclusion', 'textarea',
           help_text='Final conclusion and recommendations'),
    _field('job_photos', 'photos',
           help_text='General job photos'),
]


class RoofReportSubmitSerializer(serializers.ModelSerializer):
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
        model = RoofReportSubmission
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
        if self.context['job_report'].is_submitted:
            raise serializers.ValidationError('This report has already been submitted.')
        return data

    def create(self, validated_data):
        front_photos = validated_data.pop('front_of_dwelling', [])
        damage_photos = validated_data.pop('damage_photos', [])
        job_photos = validated_data.pop('job_photos', [])
        job_report = self.context['job_report']
        user = self.context['request'].user

        submission = RoofReportSubmission.objects.create(
            job_report=job_report,
            submitted_by=user,
            snapshot=_build_snapshot(job_report),
            **validated_data
        )
        ct = ContentType.objects.get_for_model(RoofReportSubmission)
        _save_photos(ct, submission.id, front_photos, 'front_of_dwelling')
        _save_photos(ct, submission.id, damage_photos, 'damage_photo')
        _save_photos(ct, submission.id, job_photos, 'job_photo')

        job_report.is_submitted = True
        job_report.submitted_by = user
        job_report.submitted_at = timezone.now()
        job_report.save()
        return submission


class RoofReportReadSerializer(serializers.ModelSerializer):
    photos = serializers.SerializerMethodField()
    submitted_by_name = serializers.CharField(source='submitted_by.full_name', read_only=True)

    class Meta:
        model = RoofReportSubmission
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
        ct = ContentType.objects.get_for_model(RoofReportSubmission)
        photos = ReportPhoto.objects.filter(content_type=ct, object_id=obj.id)
        request = self.context.get('request')
        result = {}
        for photo in photos:
            url = request.build_absolute_uri(photo.image.url) if request and photo.image else None
            result.setdefault(photo.photo_type, []).append({
                'id': str(photo.id), 'url': url, 'uploaded_at': photo.uploaded_at,
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
        return {}

    def get_submission(self, obj):
        if not obj.is_submitted:
            return None
        try:
            return ApplianceReportReadSerializer(
                obj.appliance_submission, context=self.context
            ).data
        except ApplianceReportSubmission.DoesNotExist:
            return None


APPLIANCE_FORM_FIELDS = [
    _field('attendance_datetime', 'datetime', required=True,
           help_text='Date and time of attendance on site'),
    _field('front_of_property', 'photos',
           help_text='Photos of the front of the property'),
    _field('discussion_with_insured', 'textarea',
           help_text='Notes from discussion with insured'),
    _field('appliance_brand', 'text',
           help_text='Brand name of the appliance'),
    _field('model_no', 'text',
           help_text='Model number of the appliance'),
    _field('approx_age', 'text',
           help_text="Approximate age of the appliance e.g. '5 years'"),
    _field('conclusion', 'textarea',
           help_text='Final conclusion and recommendations'),
    _field('job_photos', 'photos',
           help_text='General job photos'),
]


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
        _save_photos(ct, submission.id, front_photos, 'front_of_property')
        _save_photos(ct, submission.id, job_photos, 'job_photo')

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
            return DrainInspectionReadSerializer(
                obj.drain_submission, context=self.context
            ).data
        except DrainInspectionSubmission.DoesNotExist:
            return None


DRAIN_FORM_FIELDS = [
    _field('attendance_datetime', 'datetime', required=True,
           help_text='Date and time of attendance on site'),
    _field('front_of_dwelling', 'photos',
           help_text='Photos of the front of the dwelling'),
    _field('property_construction', 'select', choices=_choices_list(PropertyConstruction),
           help_text='Type of property construction'),
    _field('discussion_with_insured', 'textarea',
           help_text='Notes from discussion with insured'),
    _field('resultant_damage', 'textarea',
           help_text='Description of resultant damage'),
    _field('damage_photos', 'photos',
           help_text='Photos of damage areas'),
    _field('area_of_inspection', 'select', choices=_choices_list(AreaOfInspection),
           help_text='Area being inspected'),
    _field('pipe_construction', 'select', choices=_choices_list(PipeConstruction),
           help_text='Type of pipe construction'),
    _field('conclusion', 'textarea',
           help_text='Final conclusion and recommendations'),
    _field('job_photos', 'photos',
           help_text='General job photos'),
]


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
        _save_photos(ct, submission.id, front_photos, 'front_of_dwelling')
        _save_photos(ct, submission.id, damage_photos, 'damage_photo')
        _save_photos(ct, submission.id, job_photos, 'job_photo')

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
            return LeakInspectionReadSerializer(
                obj.leak_submission, context=self.context
            ).data
        except LeakInspectionSubmission.DoesNotExist:
            return None


LEAK_FORM_FIELDS = [
    _field('attendance_datetime', 'datetime', required=True,
           help_text='Date and time of attendance on site'),
    _field('front_of_dwelling', 'photos',
           help_text='Photos of the front of the dwelling'),
    _field('property_construction', 'select', choices=_choices_list(PropertyConstruction),
           help_text='Type of property construction'),
    _field('discussion_with_site_contact', 'textarea',
           help_text='Notes from discussion with site contact'),
    _field('resultant_damage', 'textarea',
           help_text='Description of resultant damage'),
    _field('damage_photos', 'photos',
           help_text='Photos of damage areas'),
    _field('testing_location', 'select', choices=_choices_list(TestingLocation),
           help_text='Location being tested'),
    _field('whole_area_photo', 'photo',
           help_text='Single photo of the whole area being tested'),
    _field('pressure_cold_line', 'select', choices=_choices_list(PassFailNA),
           help_text='Pressure test — cold line'),
    _field('pressure_hot_line', 'select', choices=_choices_list(PassFailNA),
           help_text='Pressure test — hot line'),
    _field('pressure_shower_breech', 'select', choices=_choices_list(PassFailNA),
           help_text='Pressure test — shower breech/mixer'),
    _field('pressure_bath_breech', 'select', choices=_choices_list(PassFailNA),
           help_text='Pressure test — bath breech/mixer'),
    _field('test_results_photo', 'photo',
           help_text='Single photo of the pressure test gauge/results'),
    _field('flood_test_shower', 'select', choices=_choices_list(PassFailNA),
           help_text='Flood test — shower alcove'),
    _field('flood_test_bath', 'select', choices=_choices_list(PassFailNA),
           help_text='Flood test — bath'),
    _field('spray_test_wall_tiles', 'select', choices=_choices_list(PassFailNA),
           help_text='Spray test — wall tiles'),
    _field('spray_test_shower_screen', 'select', choices=_choices_list(PassFailNA),
           help_text='Spray test — shower screen'),
    _field('tile_condition', 'select', choices=_choices_list(ConditionRating),
           help_text='Condition rating of tiles'),
    _field('grout_condition', 'select', choices=_choices_list(ConditionRating),
           help_text='Condition rating of grout'),
    _field('silicone_condition', 'select', choices=_choices_list(ConditionRating),
           help_text='Condition rating of silicone'),
    _field('silicone_around_spindles', 'boolean',
           help_text='Is silicone present around spindles and penetrations?'),
    _field('spindle_photos', 'photos',
           help_text='Photos of spindles/mixers'),
    _field('conclusion', 'textarea',
           help_text='Final conclusion and recommendations'),
    _field('job_photos', 'photos',
           help_text='General job photos'),
]


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
        _save_photos(ct, submission.id, front_photos, 'front_of_dwelling')
        _save_photos(ct, submission.id, damage_photos, 'damage_photo')
        _save_photos(ct, submission.id, spindle_photos, 'spindle_photo')
        _save_photos(ct, submission.id, job_photos, 'job_photo')
        if whole_area_photo:
            _save_photos(ct, submission.id, [whole_area_photo], 'whole_area')
        if test_results_photo:
            _save_photos(ct, submission.id, [test_results_photo], 'test_results')

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
            return SprayTestReadSerializer(obj.spray_submission, context=self.context).data
        except SprayTestSubmission.DoesNotExist:
            return None


SPRAY_FORM_FIELDS = [
    _field('attendance_datetime', 'datetime', required=True,
           help_text='Date and time of attendance on site'),
    _field('front_of_dwelling', 'photos',
           help_text='Photos of the front of the dwelling'),
    _field('property_construction', 'select', choices=_choices_list(PropertyConstruction),
           help_text='Type of property construction'),
    _field('discussion_with_insured', 'textarea',
           help_text='Notes from discussion with insured'),
    _field('resultant_damage', 'textarea',
           help_text='Description of resultant damage'),
    _field('damage_photos', 'photos',
           help_text='Photos of damage areas'),
    _field('testing_location', 'select', choices=_choices_list(SprayTestLocation),
           help_text='Location being tested'),
    _field('whole_area_photo', 'photo',
           help_text='Single photo of the whole area'),
    _field('flood_test', 'select', choices=_choices_list(PassFailNA),
           help_text='Flood test result'),
    _field('flood_test_notes', 'textarea',
           help_text='Notes on the flood test'),
    _field('spray_test', 'select', choices=_choices_list(PassFailNA),
           help_text='Spray test result'),
    _field('spray_test_notes', 'textarea',
           help_text='Notes on the spray test'),
    _field('tile_condition', 'select', choices=_choices_list(ConditionRating),
           help_text='Condition rating of tiles'),
    _field('tile_condition_notes', 'textarea',
           help_text='Notes on tile condition'),
    _field('grout_condition', 'select', choices=_choices_list(ConditionRating),
           help_text='Condition rating of grout'),
    _field('grout_condition_notes', 'textarea',
           help_text='Notes on grout condition'),
    _field('silicone_condition', 'select', choices=_choices_list(ConditionRating),
           help_text='Condition rating of silicone'),
    _field('silicone_condition_notes', 'textarea',
           help_text='Notes on silicone condition'),
    _field('conclusion', 'textarea',
           help_text='Final conclusion and recommendations'),
    _field('job_photos', 'photos',
           help_text='General job photos'),
]


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
        _save_photos(ct, submission.id, front_photos, 'front_of_dwelling')
        _save_photos(ct, submission.id, damage_photos, 'damage_photo')
        _save_photos(ct, submission.id, job_photos, 'job_photo')
        if whole_area_photo:
            _save_photos(ct, submission.id, [whole_area_photo], 'whole_area')

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


# ==================== FORM FIELDS REGISTRY ====================

FORM_FIELDS_REGISTRY = {
    ReportType.ROOF: ROOF_FORM_FIELDS,
    ReportType.APPLIANCE: APPLIANCE_FORM_FIELDS,
    ReportType.DRAIN_INSPECTION: DRAIN_FORM_FIELDS,
    ReportType.LEAK_INSPECTION: LEAK_FORM_FIELDS,
    ReportType.SPRAY_TEST: SPRAY_FORM_FIELDS,
}