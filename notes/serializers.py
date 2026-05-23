from rest_framework import serializers
from .models import Note, Task
from django.contrib.auth import get_user_model

User = get_user_model()


class TaskStaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name', 'email']


class TaskSerializer(serializers.ModelSerializer):
    staff = TaskStaffSerializer(read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = Task
        fields = [
            'id', 'name', 'description', 'staff',
            'due_date', 'estimated_cost',
            'created_by_name', 'created_at', 'updated_at',
        ]


class TaskWriteSerializer(serializers.ModelSerializer):
    staff_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Task
        fields = ['name', 'description', 'staff_id', 'due_date', 'estimated_cost']

    def validate_staff_id(self, value):
        if value is None:
            return value
        if not User.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError('Staff member not found or inactive.')
        return value

    def _resolve_staff(self, validated_data):
        staff_id = validated_data.pop('staff_id', 'UNCHANGED')
        if staff_id == 'UNCHANGED':
            return 'UNCHANGED'
        return User.objects.get(id=staff_id) if staff_id else None

    def create(self, validated_data):
        staff = self._resolve_staff(validated_data)
        task = Task.objects.create(**validated_data)
        if staff != 'UNCHANGED':
            task.staff = staff
            task.save(update_fields=['staff'])
        return task

    def update(self, instance, validated_data):
        staff = self._resolve_staff(validated_data)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if staff != 'UNCHANGED':
            instance.staff = staff
        instance.save()
        return instance


class NoteStaffSerializer(serializers.ModelSerializer):
    color = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'full_name', 'email', 'profile_picture', 'color']

    def get_color(self, obj):
        try:
            return obj.user_color.color
        except Exception:
            return None


class NoteSerializer(serializers.ModelSerializer):
    job = serializers.SerializerMethodField()
    staff = NoteStaffSerializer(many=True, read_only=True)
    tasks = TaskSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)

    class Meta:
        model = Note
        fields = [
            'id', 'job', 'title', 'description',
            'scheduled_datetime', 'end_time',
            'staff', 'tasks',
            'created_by_name', 'created_at', 'updated_at',
        ]

    def get_job(self, obj):
        if not obj.job:
            return None
        return {
            'id': str(obj.job.id),
            'job_id': obj.job.job_id,
            'job_name': obj.job.job_name,
            'status': obj.job.status,
        }


class NoteWriteSerializer(serializers.ModelSerializer):
    job_id = serializers.UUIDField(required=False, allow_null=True, write_only=True)
    staff_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )
    task_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, write_only=True
    )

    class Meta:
        model = Note
        fields = [
            'title', 'description', 'scheduled_datetime', 'end_time',
            'job_id', 'staff_ids', 'task_ids',
        ]

    def validate_job_id(self, value):
        if value is None:
            return value
        from jobs.models import Job
        if not Job.objects.filter(id=value).exists():
            raise serializers.ValidationError('Job not found.')
        return value

    def validate_staff_ids(self, value):
        for uid in value:
            if not User.objects.filter(id=uid, is_active=True).exists():
                raise serializers.ValidationError(f'Staff member {uid} not found or inactive.')
        return value

    def validate_task_ids(self, value):
        for tid in value:
            if not Task.objects.filter(id=tid).exists():
                raise serializers.ValidationError(f'Task {tid} not found.')
        return value

    def _set_relations(self, note, validated_data):
        from jobs.models import Job

        job_id = validated_data.pop('job_id', 'UNCHANGED')
        staff_ids = validated_data.pop('staff_ids', 'UNCHANGED')
        task_ids = validated_data.pop('task_ids', 'UNCHANGED')

        if job_id != 'UNCHANGED':
            note.job = Job.objects.get(id=job_id) if job_id else None
        note.save()

        if staff_ids != 'UNCHANGED':
            note.staff.set(User.objects.filter(id__in=staff_ids))

        if task_ids != 'UNCHANGED':
            note.tasks.set(Task.objects.filter(id__in=task_ids))

        return note

    def create(self, validated_data):
        relation_keys = ['job_id', 'staff_ids', 'task_ids']
        clean_data = {k: v for k, v in validated_data.items() if k not in relation_keys}
        note = Note.objects.create(**clean_data)
        return self._set_relations(note, validated_data)

    def update(self, instance, validated_data):
        for attr in ['title', 'description', 'scheduled_datetime', 'end_time']:
            if attr in validated_data:
                setattr(instance, attr, validated_data.pop(attr))
        return self._set_relations(instance, validated_data)
