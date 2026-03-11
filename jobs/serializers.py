from rest_framework import serializers
from django.utils import timezone
from .models import (
    Job, JobAttachment, JobLineItem, JobActivity,
    JobStatus, JobPriority, ActivityType,
    # JobPhoto,   # commented out — photos now in reports app
    # JobTask,    # commented out — tasks feature deferred
    # JobNote,    # commented out — chat feature deferred
)
from clients.serializers import ClientListSerializer
from fleets.serializers import VehicleListSerializer
from user.models import User


class JobActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)

    class Meta:
        model = JobActivity
        fields = ['id', 'activity_type', 'actor', 'actor_name', 'description', 'created_at']
        read_only_fields = fields


class JobAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)

    class Meta:
        model = JobAttachment
        fields = ['id', 'file', 'file_name', 'uploaded_by', 'uploaded_by_name', 'uploaded_at']
        read_only_fields = ['id', 'file_name', 'uploaded_by', 'uploaded_by_name', 'uploaded_at']


# ── JobPhotoSerializer — commented out ───────────────────────────────────────
# class JobPhotoSerializer(serializers.ModelSerializer):
#     uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)
#     class Meta:
#         model = JobPhoto
#         fields = ['id', 'image', 'caption', 'uploaded_by', 'uploaded_by_name', 'uploaded_at']
#         read_only_fields = ['id', 'uploaded_by', 'uploaded_by_name', 'uploaded_at']


class JobLineItemSerializer(serializers.ModelSerializer):
    total = serializers.ReadOnlyField()

    class Meta:
        model = JobLineItem
        fields = ['id', 'item', 'quantity', 'unit_price', 'total', 'order']
        read_only_fields = ['id', 'total']


# ── JobTaskSerializer — commented out ────────────────────────────────────────
# class JobTaskSerializer(serializers.ModelSerializer):
#     completed_by_name = serializers.CharField(source='completed_by.full_name', read_only=True)
#     class Meta:
#         model = JobTask
#         fields = [
#             'id', 'description', 'is_done',
#             'completed_by', 'completed_by_name',
#             'completed_at', 'order'
#         ]
#         read_only_fields = ['id', 'completed_by', 'completed_by_name', 'completed_at']


# ── JobNoteSerializer — commented out ────────────────────────────────────────
# class JobNoteSerializer(serializers.ModelSerializer):
#     sender_name = serializers.CharField(source='sender.full_name', read_only=True)
#     sender_role = serializers.CharField(source='sender.role', read_only=True)
#     class Meta:
#         model = JobNote
#         fields = [
#             'id', 'sender', 'sender_name', 'sender_role',
#             'message', 'is_system_message', 'created_at'
#         ]
#         read_only_fields = ['id', 'sender', 'sender_name', 'sender_role',
#                             'is_system_message', 'created_at']
#
# class JobNoteCreateSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = JobNote
#         fields = ['message']


# ==================== ASSIGNED USER SERIALIZERS ====================

class AssignedEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone', 'profile_picture']


class AssignedManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone']


# ==================== REPORT SUMMARY (used inside job serializers) ====================

class JobReportSummarySerializer(serializers.Serializer):
    """
    Lightweight report summary nested inside job detail responses.
    Gives the frontend the job_report_id it needs to call report endpoints.
    """
    job_report_id = serializers.UUIDField(source='id')
    report_type = serializers.CharField()
    report_type_display = serializers.CharField(source='get_report_type_display')
    is_submitted = serializers.BooleanField()
    submitted_at = serializers.DateTimeField(allow_null=True)


# ==================== JOB SERIALIZERS ====================

class JobListSerializer(serializers.ModelSerializer):
    """Lightweight — for list views and calendar."""
    assigned_to = AssignedEmployeeSerializer(read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_address = serializers.CharField(source='client.address', read_only=True)
    is_overdue = serializers.ReadOnlyField()
    has_fleet_issue = serializers.ReadOnlyField()
    safety_form_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'job_id', 'status', 'priority', 'job_name',
            'scheduled_datetime',
            'client', 'client_name', 'client_address',
            'assigned_to', 'is_overdue', 'has_fleet_issue',
            'safety_form_count',
            'created_at'
        ]

    def get_safety_form_count(self, obj):
        return obj.safety_forms.count()


class JobDetailSerializer(serializers.ModelSerializer):
    """Full detail — all nested data. Used by admin/manager."""
    assigned_to = AssignedEmployeeSerializer(read_only=True)
    assigned_managers = AssignedManagerSerializer(many=True, read_only=True)
    client = ClientListSerializer(read_only=True)
    vehicle = VehicleListSerializer(read_only=True)
    attachments = JobAttachmentSerializer(many=True, read_only=True)
    line_items = JobLineItemSerializer(many=True, read_only=True)
    activities = JobActivitySerializer(many=True, read_only=True)
    safety_forms = serializers.SerializerMethodField()
    reports = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    is_overdue = serializers.ReadOnlyField()
    has_fleet_issue = serializers.ReadOnlyField()

    class Meta:
        model = Job
        fields = [
            'id', 'job_id', 'status', 'priority', 'job_name',
            'job_details',
            'scheduled_datetime',
            'client', 'assigned_to', 'assigned_managers',
            'vehicle', 'safety_forms', 'reports',
            'attachments', 'line_items',
            'activities',
            'grand_total', 'is_overdue', 'has_fleet_issue',
            'created_at', 'updated_at'
        ]

    def get_safety_forms(self, obj):
        from safety_forms.serializers import SafetyFormTemplateListSerializer
        return SafetyFormTemplateListSerializer(obj.safety_forms.all(), many=True).data

    def get_reports(self, obj):
        # Import here to avoid circular imports
        job_reports = obj.job_reports.all().order_by('created_at')
        return JobReportSummarySerializer(job_reports, many=True).data

    def get_grand_total(self, obj):
        return sum(item.total for item in obj.line_items.all())


class JobWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates or updates a job.
    All relation fields accept PKs/UUIDs.
    report_type_ids accepts a list of report type strings e.g. ['root', 'appliance']
    and creates JobReport records in the same transaction.
    """
    assigned_to_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    assigned_manager_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    vehicle_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    client_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    safety_form_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        write_only=True
    )
    report_type_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True,
        help_text="List of report type strings e.g. ['root', 'appliance']"
    )

    class Meta:
        model = Job
        fields = [
            'job_name', 'job_details',
            'priority',
            'scheduled_datetime',
            'client_id', 'assigned_to_id', 'assigned_manager_ids',
            'vehicle_id', 'safety_form_ids', 'report_type_ids',
        ]

    def validate_assigned_to_id(self, value):
        if value is None:
            return value
        try:
            user = User.objects.get(id=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('Employee not found.')
        if user.is_staff or user.is_superuser:
            raise serializers.ValidationError('Only employees can be assigned to jobs.')
        return value

    def validate_assigned_manager_ids(self, value):
        for uid in value:
            try:
                user = User.objects.get(id=uid)
            except User.DoesNotExist:
                raise serializers.ValidationError(f'Manager {uid} not found.')
            if not (user.is_staff and not user.is_superuser):
                raise serializers.ValidationError(f'User {uid} is not a manager.')
        return value

    def validate_vehicle_id(self, value):
        if value is None:
            return value
        from fleets.models import Vehicle
        if not Vehicle.objects.filter(id=value).exists():
            raise serializers.ValidationError('Vehicle not found.')
        return value

    def validate_client_id(self, value):
        if value is None:
            return value
        from clients.models import Client
        if not Client.objects.filter(id=value).exists():
            raise serializers.ValidationError('Client not found.')
        return value

    def validate_safety_form_ids(self, value):
        from safety_forms.models import SafetyFormTemplate
        for fid in value:
            if not SafetyFormTemplate.objects.filter(id=fid, is_active=True).exists():
                raise serializers.ValidationError(f'Safety form {fid} not found or inactive.')
        return value

    def validate_report_type_ids(self, value):
        from reports.models import ReportType
        valid = [choice[0] for choice in ReportType.choices]
        for rt in value:
            if rt not in valid:
                raise serializers.ValidationError(
                    f'"{rt}" is not a valid report type. Valid choices: {valid}'
                )
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Duplicate report types are not allowed.')
        return value

    def _set_relations(self, job, validated_data, is_create=False):
        from fleets.models import Vehicle
        from clients.models import Client
        from safety_forms.models import SafetyFormTemplate
        from reports.models import JobReport

        assigned_to_id = validated_data.pop('assigned_to_id', 'UNCHANGED')
        assigned_manager_ids = validated_data.pop('assigned_manager_ids', 'UNCHANGED')
        vehicle_id = validated_data.pop('vehicle_id', 'UNCHANGED')
        client_id = validated_data.pop('client_id', 'UNCHANGED')
        safety_form_ids = validated_data.pop('safety_form_ids', 'UNCHANGED')
        report_type_ids = validated_data.pop('report_type_ids', 'UNCHANGED')

        if assigned_to_id != 'UNCHANGED':
            job.assigned_to = User.objects.get(id=assigned_to_id) if assigned_to_id else None

        if vehicle_id != 'UNCHANGED':
            job.vehicle = Vehicle.objects.get(id=vehicle_id) if vehicle_id else None

        if client_id != 'UNCHANGED':
            job.client = Client.objects.get(id=client_id) if client_id else None

        job.save()

        if assigned_manager_ids != 'UNCHANGED':
            managers = User.objects.filter(id__in=assigned_manager_ids)
            job.assigned_managers.set(managers)

        if safety_form_ids != 'UNCHANGED':
            forms = SafetyFormTemplate.objects.filter(id__in=safety_form_ids)
            job.safety_forms.set(forms)

        if report_type_ids != 'UNCHANGED':
            if is_create:
                # On create: bulk-create all JobReport records
                JobReport.objects.bulk_create([
                    JobReport(job=job, report_type=rt)
                    for rt in report_type_ids
                ])
            else:
                # On update: add new ones, leave existing submissions untouched
                existing = set(
                    job.job_reports.values_list('report_type', flat=True)
                )
                new_types = set(report_type_ids)
                # Add newly requested types
                to_add = new_types - existing
                JobReport.objects.bulk_create([
                    JobReport(job=job, report_type=rt)
                    for rt in to_add
                ])
                # Remove types no longer requested — only if not yet submitted
                to_remove = existing - new_types
                job.job_reports.filter(
                    report_type__in=to_remove,
                    is_submitted=False
                ).delete()

        return job

    def create(self, validated_data):
        # Pop all relation fields before creating the Job instance
        relation_keys = [
            'assigned_to_id', 'assigned_manager_ids',
            'vehicle_id', 'client_id', 'safety_form_ids', 'report_type_ids'
        ]
        clean_data = {k: v for k, v in validated_data.items() if k not in relation_keys}
        job = Job.objects.create(**clean_data)
        return self._set_relations(job, validated_data, is_create=True)

    def update(self, instance, validated_data):
        scalar_fields = ['job_name', 'job_details', 'priority', 'scheduled_datetime']
        for attr in scalar_fields:
            if attr in validated_data:
                setattr(instance, attr, validated_data.pop(attr))
        return self._set_relations(instance, validated_data, is_create=False)


class JobScheduleSerializer(serializers.ModelSerializer):
    """Dedicated for drag-and-drop calendar reschedule. Only updates scheduled_datetime."""
    class Meta:
        model = Job
        fields = ['scheduled_datetime']

    def update(self, instance, validated_data):
        old_dt = instance.scheduled_datetime
        instance.scheduled_datetime = validated_data['scheduled_datetime']
        instance.save()
        JobActivity.objects.create(
            job=instance,
            activity_type=ActivityType.JOB_RESCHEDULED,
            actor=self.context['request'].user,
            description=f"Rescheduled from {old_dt} to {instance.scheduled_datetime}"
        )
        return instance


class JobStatusUpdateSerializer(serializers.ModelSerializer):
    """Employee uses this to update job status (start, complete etc.)."""
    class Meta:
        model = Job
        fields = ['status']

    def validate_status(self, value):
        instance = self.instance
        user = self.context['request'].user
        allowed_transitions = {
            JobStatus.PENDING: [JobStatus.IN_PROGRESS],
            JobStatus.IN_PROGRESS: [JobStatus.COMPLETED],
            JobStatus.OVERDUE: [JobStatus.COMPLETED],
        }
        allowed = allowed_transitions.get(instance.status, [])
        if value not in allowed:
            raise serializers.ValidationError(
                f'Cannot transition from "{instance.status}" to "{value}".'
            )
        if not user.is_superuser and instance.assigned_to != user:
            raise serializers.ValidationError('You are not assigned to this job.')
        return value

    def update(self, instance, validated_data):
        new_status = validated_data['status']
        instance.status = new_status
        instance.save()
        activity_map = {
            JobStatus.IN_PROGRESS: ActivityType.JOB_STARTED,
            JobStatus.COMPLETED: ActivityType.JOB_COMPLETED,
        }
        activity_type = activity_map.get(new_status, ActivityType.STATUS_CHANGED)
        JobActivity.objects.create(
            job=instance,
            activity_type=activity_type,
            actor=self.context['request'].user,
            description=f"Status changed to {new_status}"
        )
        return instance


class JobDashboardSerializer(serializers.Serializer):
    """Summary counts for the admin/manager dashboard."""
    total_jobs = serializers.IntegerField()
    active_jobs = serializers.IntegerField()
    jobs_today = serializers.IntegerField()
    pending_jobs = serializers.IntegerField()
    completed_jobs = serializers.IntegerField()
    overdue_jobs = serializers.IntegerField()
    pending_safety_forms = serializers.IntegerField()
    fleet_issues = serializers.IntegerField()


# ==================== EMPLOYEE-FACING SERIALIZERS ====================

class JobMinimalSerializer(serializers.ModelSerializer):
    """Minimal job card for list views and calendar."""
    client_address = serializers.CharField(source='client.address', read_only=True)
    vehicle_name = serializers.CharField(source='vehicle.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)

    class Meta:
        model = Job
        fields = [
            'id', 'job_id', 'job_name',
            'client_address', 'scheduled_datetime',
            'vehicle_name', 'vehicle_plate',
            'status',
        ]


class EmployeeJobDetailSerializer(serializers.ModelSerializer):
    """
    Full job detail for employee-facing detail endpoint.
    Contains everything the mobile app needs to render the job screen.
    Includes attached reports so the employee can navigate to submit them.
    """
    client_info = serializers.SerializerMethodField()
    assigned_employee_info = serializers.SerializerMethodField()
    vehicle_name = serializers.CharField(source='vehicle.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    attachments = JobAttachmentSerializer(many=True, read_only=True)
    safety_form_ids = serializers.SerializerMethodField()
    reports = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'job_id', 'job_name', 'job_details',
            'status', 'priority', 'scheduled_datetime',
            'vehicle_name', 'vehicle_plate',
            'client_info', 'assigned_employee_info',
            'attachments',
            'reports',
            'safety_form_ids',
            'created_at', 'updated_at',
        ]

    def get_client_info(self, obj):
        if not obj.client:
            return None
        return {
            'name': obj.client.name,
            'email': obj.client.email,
            'phone': obj.client.phone,
            'profile_picture': self._get_image_url(obj.client.profile_picture),
            'contact_person_name': obj.client.contact_person_name,
            'address': obj.client.address,
            'maps_url': obj.client.maps_url,
        }

    def get_assigned_employee_info(self, obj):
        if not obj.assigned_to:
            return None
        request = self.context.get('request')
        pic = obj.assigned_to.profile_picture
        return {
            'id': str(obj.assigned_to.id),
            'full_name': obj.assigned_to.full_name,
            'phone': str(obj.assigned_to.phone) if obj.assigned_to.phone else None,
            'email': obj.assigned_to.email,
            'profile_picture': request.build_absolute_uri(pic.url) if pic and request else None,
        }

    def get_safety_form_ids(self, obj):
        return [str(uid) for uid in obj.safety_forms.values_list('id', flat=True)]

    def get_reports(self, obj):
        """
        Returns attached report summaries so employee sees what reports
        are pending/submitted and gets the job_report_id to navigate to each.
        """
        job_reports = obj.job_reports.all().order_by('created_at')
        return JobReportSummarySerializer(job_reports, many=True).data

    def _get_image_url(self, image_field):
        request = self.context.get('request')
        if image_field and request:
            return request.build_absolute_uri(image_field.url)
        return None


class EmployeeJobListResponseSerializer(serializers.Serializer):
    """Response shape for the today/upcoming/completed endpoint."""
    today = JobMinimalSerializer(many=True)
    upcoming = JobMinimalSerializer(many=True)
    completed = JobMinimalSerializer(many=True)


class EmployeeCalendarJobsSerializer(serializers.Serializer):
    """Response shape for the calendar today/tomorrow/this week endpoint."""
    today = JobMinimalSerializer(many=True)
    tomorrow = JobMinimalSerializer(many=True)
    this_week = JobMinimalSerializer(many=True)