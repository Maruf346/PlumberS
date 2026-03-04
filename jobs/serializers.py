from rest_framework import serializers
from django.utils import timezone
from .models import *
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


class JobPhotoSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.full_name', read_only=True)

    class Meta:
        model = JobPhoto
        fields = ['id', 'image', 'caption', 'uploaded_by', 'uploaded_by_name', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_by', 'uploaded_by_name', 'uploaded_at']


class JobLineItemSerializer(serializers.ModelSerializer):
    total = serializers.ReadOnlyField()

    class Meta:
        model = JobLineItem
        fields = ['id', 'item', 'quantity', 'unit_price', 'total', 'order']
        read_only_fields = ['id', 'total']


class JobTaskSerializer(serializers.ModelSerializer):
    completed_by_name = serializers.CharField(source='completed_by.full_name', read_only=True)

    class Meta:
        model = JobTask
        fields = [
            'id', 'description', 'is_done',
            'completed_by', 'completed_by_name',
            'completed_at', 'order'
        ]
        read_only_fields = ['id', 'completed_by', 'completed_by_name', 'completed_at']


class JobNoteSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_role = serializers.CharField(source='sender.role', read_only=True)

    class Meta:
        model = JobNote
        fields = [
            'id', 'sender', 'sender_name', 'sender_role',
            'message', 'is_system_message', 'created_at'
        ]
        read_only_fields = ['id', 'sender', 'sender_name', 'sender_role', 'is_system_message', 'created_at']


class JobNoteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobNote
        fields = ['message']


# ==================== ASSIGNED USER SERIALIZERS ====================

class AssignedEmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone', 'profile_picture']


class AssignedManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone']


# ==================== JOB SERIALIZERS ====================

class JobListSerializer(serializers.ModelSerializer):
    """Lightweight — for list views and calendar."""
    assigned_to = AssignedEmployeeSerializer(read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_address = serializers.CharField(source='client.address', read_only=True)
    is_overdue = serializers.ReadOnlyField()
    has_fleet_issue = serializers.ReadOnlyField()
    safety_form_count = serializers.SerializerMethodField()
    task_count = serializers.SerializerMethodField()
    completed_task_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'job_id', 'status', 'priority',
            'insured_name', 'scheduled_datetime',
            'client', 'client_name', 'client_address',
            'assigned_to', 'is_overdue', 'has_fleet_issue',
            'safety_form_count', 'task_count', 'completed_task_count',
            'created_at'
        ]

    def get_safety_form_count(self, obj):
        return obj.safety_forms.count()

    def get_task_count(self, obj):
        return obj.tasks.count()

    def get_completed_task_count(self, obj):
        return obj.tasks.filter(is_done=True).count()


class JobDetailSerializer(serializers.ModelSerializer):
    """Full detail — all nested data."""
    assigned_to = AssignedEmployeeSerializer(read_only=True)
    assigned_managers = AssignedManagerSerializer(many=True, read_only=True)
    client = ClientListSerializer(read_only=True)
    vehicle = VehicleListSerializer(read_only=True)
    attachments = JobAttachmentSerializer(many=True, read_only=True)
    photos = JobPhotoSerializer(many=True, read_only=True)
    line_items = JobLineItemSerializer(many=True, read_only=True)
    tasks = JobTaskSerializer(many=True, read_only=True)
    notes = JobNoteSerializer(many=True, read_only=True)
    activities = JobActivitySerializer(many=True, read_only=True)
    safety_forms = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    is_overdue = serializers.ReadOnlyField()
    has_fleet_issue = serializers.ReadOnlyField()

    class Meta:
        model = Job
        fields = [
            'id', 'job_id', 'status', 'priority',
            'job_details', 'insured_name',
            'scheduled_datetime',
            'client', 'assigned_to', 'assigned_managers',
            'vehicle', 'safety_forms', 'report_template_ids',
            'attachments', 'photos', 'line_items', 'tasks',
            'notes', 'activities',
            'grand_total', 'is_overdue', 'has_fleet_issue',
            'created_at', 'updated_at'
        ]

    def get_safety_forms(self, obj):
        from safety_forms.serializers import SafetyFormTemplateListSerializer
        return SafetyFormTemplateListSerializer(obj.safety_forms.all(), many=True).data

    def get_grand_total(self, obj):
        return sum(item.total for item in obj.line_items.all())


class JobWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates or updates a job.
    All relation fields accept PKs/UUIDs.
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

    class Meta:
        model = Job
        fields = [
            'job_details', 'insured_name', 'priority',
            'scheduled_datetime', 'report_template_ids',
            'client_id', 'assigned_to_id', 'assigned_manager_ids',
            'vehicle_id', 'safety_form_ids',
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
            if not user.is_staff or user.is_superuser:
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

    def _set_relations(self, job, validated_data):
        from fleets.models import Vehicle
        from clients.models import Client
        from safety_forms.models import SafetyFormTemplate

        assigned_to_id = validated_data.pop('assigned_to_id', 'UNCHANGED')
        assigned_manager_ids = validated_data.pop('assigned_manager_ids', 'UNCHANGED')
        vehicle_id = validated_data.pop('vehicle_id', 'UNCHANGED')
        client_id = validated_data.pop('client_id', 'UNCHANGED')
        safety_form_ids = validated_data.pop('safety_form_ids', 'UNCHANGED')

        if assigned_to_id != 'UNCHANGED':
            job.assigned_to = User.objects.get(id=assigned_to_id) if assigned_to_id else None
            # Auto-set status to pending if unassigned, keep in_progress if already started
            if not assigned_to_id and job.status == JobStatus.PENDING:
                job.status = JobStatus.PENDING

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

        return job

    def create(self, validated_data):
        job = Job.objects.create(**{
            k: v for k, v in validated_data.items()
            if k not in [
                'assigned_to_id', 'assigned_manager_ids',
                'vehicle_id', 'client_id', 'safety_form_ids'
            ]
        })
        return self._set_relations(job, validated_data)

    def update(self, instance, validated_data):
        for attr in ['job_details', 'insured_name', 'priority', 'scheduled_datetime', 'report_template_ids']:
            if attr in validated_data:
                setattr(instance, attr, validated_data.pop(attr))
        return self._set_relations(instance, validated_data)


class JobScheduleSerializer(serializers.ModelSerializer):
    """
    Dedicated serializer for the drag-and-drop calendar reschedule endpoint.
    Only updates scheduled_datetime.
    """
    class Meta:
        model = Job
        fields = ['scheduled_datetime']

    def update(self, instance, validated_data):
        old_dt = instance.scheduled_datetime
        instance.scheduled_datetime = validated_data['scheduled_datetime']
        instance.save()
        # Log rescheduling activity
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
            JobStatus.OVERDUE: [JobStatus.IN_PROGRESS],
        }
        allowed = allowed_transitions.get(instance.status, [])
        if value not in allowed:
            raise serializers.ValidationError(
                f'Cannot transition from "{instance.status}" to "{value}".'
            )
        # Only assigned employee or admin can change status
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