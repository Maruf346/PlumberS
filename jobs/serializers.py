from rest_framework import serializers
from django.utils import timezone
from .models import (
    Job, JobAttachment, JobLineItem, JobActivity, JobNote,
    JobStatus, JobPriority, ActivityType,
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


class JobLineItemSerializer(serializers.ModelSerializer):
    total = serializers.ReadOnlyField()

    class Meta:
        model = JobLineItem
        fields = ['id', 'item', 'quantity', 'unit_price', 'total', 'order']
        read_only_fields = ['id', 'total']


class JobNoteSerializer(serializers.ModelSerializer):
    """Read serializer — used in list responses."""
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_role = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = JobNote
        fields = [
            'id', 'sender', 'sender_name', 'sender_role',
            'message', 'is_mine', 'created_at',
        ]
        read_only_fields = fields

    def get_sender_role(self, obj):
        if not obj.sender:
            return 'unknown'
        if obj.sender.is_superuser:
            return 'admin'
        if obj.sender.is_staff:
            return 'manager'
        return 'employee'

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if not request or not obj.sender:
            return False
        return obj.sender.id == request.user.id


class JobNoteCreateSerializer(serializers.Serializer):
    """Write serializer — only accepts the message text."""
    message = serializers.CharField(
        min_length=1,
        max_length=2000,
        trim_whitespace=True,
        error_messages={
            'blank': 'Message cannot be empty.',
            'max_length': 'Message cannot exceed 2000 characters.',
        }
    )


# ==================== ASSIGNED USER SERIALIZERS ====================

class AssignedEmployeeSerializer(serializers.ModelSerializer):
    color = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone', 'profile_picture', 'color']

    def get_color(self, obj):
        try:
            return obj.user_color.color
        except Exception:
            return None


class AssignedManagerSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'phone']


# ==================== REPORT SUMMARY (used inside job serializers) ====================

class JobReportSummarySerializer(serializers.Serializer):
    job_report_id = serializers.UUIDField(source='id')
    report_type = serializers.CharField()
    report_type_display = serializers.CharField(source='get_report_type_display')
    is_submitted = serializers.BooleanField()
    submitted_at = serializers.DateTimeField(allow_null=True)


# ==================== FLAT LIST SERIALIZERS (Note-based) ====================

class JobListSerializer(serializers.Serializer):
    """
    Flat list item — one entry per Note-Job pair.
    Views build SimpleNamespace objects and pass them here.
    scheduled_datetime and end_time come from the Note, all other fields from the Job.
    """
    id = serializers.UUIDField()
    note_id = serializers.UUIDField(allow_null=True)
    job_id = serializers.CharField()
    status = serializers.CharField()
    priority = serializers.CharField()
    job_name = serializers.CharField()
    insured_name = serializers.CharField()
    insured_phone = serializers.CharField()
    insured_email = serializers.CharField()
    insured_address = serializers.CharField()
    site_access_info = serializers.CharField()
    scheduled_datetime = serializers.DateTimeField(allow_null=True)
    end_time = serializers.DateTimeField(allow_null=True)
    vehicle_name = serializers.CharField(allow_null=True)
    client = serializers.UUIDField(allow_null=True)
    client_name = serializers.CharField(allow_null=True)
    client_address = serializers.CharField(allow_null=True)
    assigned_to = AssignedEmployeeSerializer(allow_null=True)
    is_overdue = serializers.BooleanField()
    has_fleet_issue = serializers.BooleanField()
    safety_form_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class JobMinimalSerializer(serializers.Serializer):
    """Minimal list item for employee views — one entry per Note-Job pair."""
    id = serializers.UUIDField()
    note_id = serializers.UUIDField(allow_null=True)
    job_id = serializers.CharField()
    job_name = serializers.CharField()
    client_address = serializers.CharField(allow_null=True)
    scheduled_datetime = serializers.DateTimeField(allow_null=True)
    end_time = serializers.DateTimeField(allow_null=True)
    vehicle_name = serializers.CharField(allow_null=True)
    vehicle_plate = serializers.CharField(allow_null=True)
    status = serializers.CharField()
    insured_name = serializers.CharField()
    insured_phone = serializers.CharField()
    insured_email = serializers.CharField()
    insured_address = serializers.CharField()
    site_access_info = serializers.CharField()


# ==================== ADMIN JOB NOTES + TASKS OVERVIEW ====================

class AdminJobTaskOverviewSerializer(serializers.Serializer):
    """
    A Task as seen inside a Note, for the admin notes+tasks overview endpoint.
    """
    id = serializers.UUIDField()
    name = serializers.CharField()
    description = serializers.CharField()
    due_date = serializers.DateField(allow_null=True)
    estimated_cost = serializers.DecimalField(max_digits=10, decimal_places=2, allow_null=True)
    staff = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_staff(self, obj):
        if not obj.staff:
            return None
        return {
            'id': str(obj.staff.id),
            'full_name': obj.staff.full_name,
            'email': obj.staff.email,
        }

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None


class AdminJobNoteOverviewSerializer(serializers.Serializer):
    """
    A Note (schedule slot) with its full staff list and all linked Tasks,
    for the admin notes+tasks overview endpoint.
    """
    note_id = serializers.UUIDField(source='id')
    title = serializers.CharField()
    description = serializers.CharField()
    scheduled_datetime = serializers.DateTimeField(allow_null=True)
    end_time = serializers.DateTimeField(allow_null=True)
    staff = serializers.SerializerMethodField()
    tasks = AdminJobTaskOverviewSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_staff(self, obj):
        return [
            {
                'id': str(u.id),
                'full_name': u.full_name,
                'email': u.email,
                'profile_picture': u.profile_picture.url if u.profile_picture else None,
            }
            for u in obj.staff.all()
        ]

    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None


class AdminJobNotesAndTasksSerializer(serializers.Serializer):
    """
    Admin-only overview: all Notes and Tasks for a job.
    Returns:
      - job_id / id / job_name / status — quick job identifiers
      - notes: list of Note schedule slots, each with their staff and tasks
      - task_summary: flat de-duplicated list of every Task across all notes
    """
    id = serializers.UUIDField()
    job_id = serializers.CharField()
    job_name = serializers.CharField()
    status = serializers.CharField()
    priority = serializers.CharField()
    notes_count = serializers.IntegerField()
    tasks_count = serializers.IntegerField()
    notes = AdminJobNoteOverviewSerializer(many=True)
    task_summary = AdminJobTaskOverviewSerializer(many=True)


# ==================== JOB DETAIL SERIALIZER ====================

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
    scheduled_datetime = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()
    schedules = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'job_id', 'status', 'priority', 'job_name',
            'job_details', 'scheduled_datetime', 'end_time',
            'insured_name', 'insured_phone', 'insured_email', 'insured_address', 'site_access_info',
            'client', 'assigned_to', 'assigned_managers',
            'vehicle', 'safety_forms', 'reports',
            'attachments', 'line_items', 'activities',
            'grand_total', 'is_overdue', 'has_fleet_issue',
            'schedules',
            'created_at', 'updated_at',
        ]

    def get_scheduled_datetime(self, obj):
        note = obj.notes.filter(scheduled_datetime__isnull=False).order_by('scheduled_datetime').first()
        return note.scheduled_datetime if note else None

    def get_end_time(self, obj):
        note = obj.notes.filter(scheduled_datetime__isnull=False).order_by('scheduled_datetime').first()
        return note.end_time if note else None

    def get_schedules(self, obj):
        notes = obj.notes.prefetch_related('staff', 'tasks').order_by('scheduled_datetime')
        result = []
        for note in notes:
            result.append({
                'note_id': str(note.id),
                'title': note.title,
                'description': note.description,
                'scheduled_datetime': note.scheduled_datetime,
                'end_time': note.end_time,
                'staff': AssignedEmployeeSerializer(note.staff.all(), many=True).data,
                'tasks': [
                    {
                        'id': str(t.id),
                        'name': t.name,
                        'description': t.description,
                        'due_date': t.due_date,
                        'estimated_cost': str(t.estimated_cost) if t.estimated_cost else None,
                    }
                    for t in note.tasks.all()
                ],
            })
        return result

    def get_safety_forms(self, obj):
        from safety_forms.serializers import SafetyFormTemplateListSerializer
        return SafetyFormTemplateListSerializer(obj.safety_forms.all(), many=True).data

    def get_reports(self, obj):
        job_reports = obj.job_reports.all().order_by('created_at')
        return JobReportSummarySerializer(job_reports, many=True).data

    def get_grand_total(self, obj):
        return sum(item.total for item in obj.line_items.all())


# ==================== JOB WRITE SERIALIZER ====================

class JobWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates or updates a job.
    Scheduling (datetime) is handled through Notes — not here.
    """
    assigned_to_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    assigned_manager_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )
    vehicle_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    client_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    safety_form_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )
    report_type_ids = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True,
        help_text="List of report type strings e.g. ['roof', 'appliance']"
    )

    class Meta:
        model = Job
        fields = [
            'job_name', 'job_details', 'priority',
            'insured_name', 'insured_phone', 'insured_email', 'insured_address', 'site_access_info',
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
                JobReport.objects.bulk_create([
                    JobReport(job=job, report_type=rt)
                    for rt in report_type_ids
                ])
            else:
                existing = set(job.job_reports.values_list('report_type', flat=True))
                new_types = set(report_type_ids)
                to_add = new_types - existing
                JobReport.objects.bulk_create([
                    JobReport(job=job, report_type=rt) for rt in to_add
                ])
                to_remove = existing - new_types
                job.job_reports.filter(report_type__in=to_remove, is_submitted=False).delete()

        return job

    def create(self, validated_data):
        relation_keys = [
            'assigned_to_id', 'assigned_manager_ids',
            'vehicle_id', 'client_id', 'safety_form_ids', 'report_type_ids',
        ]
        clean_data = {k: v for k, v in validated_data.items() if k not in relation_keys}
        job = Job.objects.create(**clean_data)
        return self._set_relations(job, validated_data, is_create=True)

    def update(self, instance, validated_data):
        scalar_fields = [
            'job_name', 'job_details', 'priority',
            'insured_name', 'insured_phone', 'insured_email',
            'insured_address', 'site_access_info',
        ]
        for attr in scalar_fields:
            if attr in validated_data:
                setattr(instance, attr, validated_data.pop(attr))
        return self._set_relations(instance, validated_data, is_create=False)


# ==================== STATUS SERIALIZERS ====================

class JobScheduleSerializer(serializers.Serializer):
    """Deprecated — scheduling is now done through Notes (PATCH /api/notes/{id}/)."""
    pass


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
        if not user.is_superuser and not (
            instance.assigned_to == user or
            instance.notes.filter(staff=user).exists()
        ):
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


class AdminJobStatusUpdateSerializer(serializers.ModelSerializer):
    """Admin forces a job to any status directly."""
    class Meta:
        model = Job
        fields = ['status']

    def validate_status(self, value):
        if value not in [s[0] for s in JobStatus.choices]:
            raise serializers.ValidationError(
                f'Invalid status. Valid choices: {[s[0] for s in JobStatus.choices]}'
            )
        return value

    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data['status']
        instance.status = new_status
        instance.save()
        JobActivity.objects.create(
            job=instance,
            activity_type=ActivityType.STATUS_CHANGED,
            actor=self.context['request'].user,
            description=f"Status manually changed from {old_status} to {new_status} by admin"
        )
        return instance


# ==================== DASHBOARD SERIALIZER ====================

class JobDashboardSerializer(serializers.Serializer):
    """Summary counts for the admin/manager dashboard."""
    total_jobs = serializers.IntegerField()
    active_jobs = serializers.IntegerField()
    jobs_today = serializers.IntegerField()
    scheduled_jobs = serializers.IntegerField()
    pending_jobs = serializers.IntegerField()
    in_progress_jobs = serializers.IntegerField()
    on_hold_jobs = serializers.IntegerField()
    to_invoice_jobs = serializers.IntegerField()
    completed_jobs = serializers.IntegerField()
    cancelled_jobs = serializers.IntegerField()
    emergency_make_safe_jobs = serializers.IntegerField()
    overdue_jobs = serializers.IntegerField()
    pending_safety_forms = serializers.IntegerField()
    fleet_issues = serializers.IntegerField()


# ==================== EMPLOYEE-FACING SERIALIZERS ====================

class EmployeeJobDetailSerializer(serializers.ModelSerializer):
    """
    Full job detail for employee-facing detail endpoint.
    scheduled_datetime and end_time are derived from the earliest Note.
    my_schedules lists Notes where the requesting user is in the staff.
    """
    client_info = serializers.SerializerMethodField()
    assigned_employee_info = serializers.SerializerMethodField()
    vehicle_name = serializers.CharField(source='vehicle.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    attachments = JobAttachmentSerializer(many=True, read_only=True)
    safety_form_ids = serializers.SerializerMethodField()
    reports = serializers.SerializerMethodField()
    scheduled_datetime = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()
    my_schedules = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'job_id', 'job_name', 'job_details',
            'status', 'priority', 'scheduled_datetime', 'end_time',
            'vehicle_name', 'vehicle_plate',
            'client_info', 'assigned_employee_info',
            'attachments', 'reports',
            'insured_name', 'insured_phone', 'insured_email',
            'insured_address', 'site_access_info',
            'safety_form_ids', 'my_schedules',
            'created_at', 'updated_at',
        ]

    def get_scheduled_datetime(self, obj):
        note = obj.notes.filter(scheduled_datetime__isnull=False).order_by('scheduled_datetime').first()
        return note.scheduled_datetime if note else None

    def get_end_time(self, obj):
        note = obj.notes.filter(scheduled_datetime__isnull=False).order_by('scheduled_datetime').first()
        return note.end_time if note else None

    def get_my_schedules(self, obj):
        request = self.context.get('request')
        if not request:
            return []
        user = request.user
        return [
            {
                'note_id': str(n.id),
                'title': n.title,
                'description': n.description,
                'scheduled_datetime': n.scheduled_datetime,
                'end_time': n.end_time,
            }
            for n in obj.notes.filter(staff=user).order_by('scheduled_datetime')
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
    this_week = serializers.DictField()


class RecentActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)
    job_id = serializers.CharField(source='job.job_id', read_only=True)
    job_name = serializers.CharField(source='job.job_name', read_only=True)
    job_uuid = serializers.UUIDField(source='job.id', read_only=True)
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = JobActivity
        fields = [
            'id', 'job_uuid', 'job_id', 'job_name',
            'activity_type', 'actor_name',
            'description', 'created_at', 'time_ago',
        ]
        read_only_fields = fields

    def get_time_ago(self, obj):
        diff = timezone.now() - obj.created_at
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return 'Just now'
        minutes = seconds // 60
        if minutes < 60:
            return f'{minutes} min ago'
        hours = minutes // 60
        if hours < 24:
            return f'{hours} hr ago'
        days = hours // 24
        return f'{days} day{"s" if days != 1 else ""} ago'


class EmployeeVehicleSerializer(serializers.Serializer):
    id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    plate = serializers.SerializerMethodField()
    picture = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    next_service = serializers.SerializerMethodField()
    last_inspection_date = serializers.SerializerMethodField()

    def get_id(self, obj):
        return str(obj.id)

    def get_name(self, obj):
        return obj.name

    def get_plate(self, obj):
        return obj.plate

    def get_picture(self, obj):
        request = self.context.get('request')
        if obj.picture and request:
            return request.build_absolute_uri(obj.picture.url)
        return None

    def get_status(self, obj):
        return obj.status

    def get_next_service(self, obj):
        return obj.next_service_km

    def get_last_inspection_date(self, obj):
        inspection = obj.inspections.order_by('-inspected_at').first()
        return inspection.inspected_at if inspection else None
