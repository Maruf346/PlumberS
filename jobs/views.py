from types import SimpleNamespace
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
from datetime import timedelta
from django.http import FileResponse

from .models import *
from .serializers import *
from user.permissions import IsAdmin, IsAdminOrManager, IsAdminOrManagerOrEmployee
from core.pagination import FlexiblePageNumberPagination


def _log_activity(job, activity_type, actor, description=''):
    JobActivity.objects.create(
        job=job,
        activity_type=activity_type,
        actor=actor,
        description=description
    )


def _build_note_job_entry(note, job):
    return SimpleNamespace(
        id=job.id,
        note_id=note.id,
        job_id=job.job_id,
        status=job.status,
        priority=job.priority,
        job_name=job.job_name,
        insured_name=job.insured_name or '',
        insured_phone=str(job.insured_phone) if job.insured_phone else '',
        insured_email=job.insured_email or '',
        insured_address=job.insured_address or '',
        site_access_info=job.site_access_info or '',
        scheduled_datetime=note.scheduled_datetime,
        end_time=note.end_time,
        vehicle_name=job.vehicle.name if job.vehicle else None,
        vehicle_plate=job.vehicle.plate if job.vehicle else None,
        client=job.client.id if job.client else None,
        client_name=job.client.name if job.client else None,
        client_address=job.client.address if job.client else None,
        assigned_to=job.assigned_to,
        is_overdue=job.is_overdue,
        has_fleet_issue=job.has_fleet_issue,
        safety_form_count=len(job.safety_forms.all()),
        created_at=job.created_at,
    )


def _build_job_entry_no_note(job):
    return SimpleNamespace(
        id=job.id,
        note_id=None,
        job_id=job.job_id,
        status=job.status,
        priority=job.priority,
        job_name=job.job_name,
        insured_name=job.insured_name or '',
        insured_phone=str(job.insured_phone) if job.insured_phone else '',
        insured_email=job.insured_email or '',
        insured_address=job.insured_address or '',
        site_access_info=job.site_access_info or '',
        scheduled_datetime=None,
        end_time=None,
        vehicle_name=job.vehicle.name if job.vehicle else None,
        vehicle_plate=job.vehicle.plate if job.vehicle else None,
        client=job.client.id if job.client else None,
        client_name=job.client.name if job.client else None,
        client_address=job.client.address if job.client else None,
        assigned_to=job.assigned_to,
        is_overdue=job.is_overdue,
        has_fleet_issue=job.has_fleet_issue,
        safety_form_count=len(job.safety_forms.all()),
        created_at=job.created_at,
    )


def _paginate(entries, request, serializer_class):
    paginator = FlexiblePageNumberPagination()
    page = paginator.paginate_queryset(entries, request)
    if page is not None:
        return paginator.get_paginated_response(serializer_class(page, many=True).data)
    return Response(serializer_class(entries, many=True).data)


def _job_base_qs():
    return Job.objects.select_related(
        'client', 'assigned_to', 'vehicle', 'assigned_to__user_color'
    ).prefetch_related('safety_forms', 'notes')


# ==================== DASHBOARD ====================

class JobDashboardView(APIView):
    """Admin/manager summary counts."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(tags=['jobs'], summary="Job dashboard summary")
    def get(self, request):
        from notes.models import Note as NoteModel

        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        jobs = Job.objects.all()

        active = jobs.filter(status=JobStatus.IN_PROGRESS).count()
        jobs_today = NoteModel.objects.filter(
            job__isnull=False,
            scheduled_datetime__gte=today_start,
            scheduled_datetime__lte=today_end,
        ).values('job').distinct().count()
        scheduled = jobs.filter(status=JobStatus.SCHEDULED).count()
        pending = jobs.filter(status=JobStatus.PENDING).count()
        in_progress = jobs.filter(status=JobStatus.IN_PROGRESS).count()
        on_hold = jobs.filter(status=JobStatus.ON_HOLD).count()
        to_invoice = jobs.filter(status=JobStatus.TO_INVOICE).count()
        completed = jobs.filter(status=JobStatus.COMPLETED).count()
        cancelled = jobs.filter(status=JobStatus.CANCELLED).count()
        emergency_make_safe = jobs.filter(status=JobStatus.EMERGENCY_MAKE_SAFE).count()
        overdue = jobs.filter(status=JobStatus.OVERDUE).count()

        pending_safety = jobs.filter(
            status=JobStatus.IN_PROGRESS
        ).filter(safety_forms__isnull=False).distinct().count()

        fleet_issues = jobs.filter(
            status__in=[JobStatus.PENDING, JobStatus.IN_PROGRESS]
        ).exclude(vehicle__isnull=True).filter(
            vehicle__status__in=['issue_reported', 'service_overdue', 'inspection_due']
        ).count()

        data = {
            'total_jobs': jobs.count(),
            'active_jobs': active,
            'jobs_today': jobs_today,
            'scheduled_jobs': scheduled,
            'pending_jobs': pending,
            'in_progress_jobs': in_progress,
            'on_hold_jobs': on_hold,
            'to_invoice_jobs': to_invoice,
            'completed_jobs': completed,
            'cancelled_jobs': cancelled,
            'emergency_make_safe_jobs': emergency_make_safe,
            'overdue_jobs': overdue,
            'pending_safety_forms': pending_safety,
            'fleet_issues': fleet_issues,
        }
        return Response(JobDashboardSerializer(data).data)


# ==================== JOB CRUD (ADMIN) ====================

class AdminJobListView(APIView):
    """Admin/manager sees all jobs — one entry per Note (or one entry if job has no notes)."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['jobs'],
        summary="List all jobs (admin/manager) — one row per schedule slot",
        parameters=[
            OpenApiParameter('status', str, description='Filter by job status'),
            OpenApiParameter('priority', str, description='Filter by priority'),
            OpenApiParameter('assigned_to', str, description='Filter by employee UUID'),
            OpenApiParameter('date', str, description='Filter by note scheduled date YYYY-MM-DD'),
            OpenApiParameter('search', str, description='Search by job ID, name, or client'),
        ]
    )
    def get(self, request):
        from datetime import date as date_type

        jobs_qs = _job_base_qs()

        status_filter = request.query_params.get('status')
        if status_filter:
            jobs_qs = jobs_qs.filter(status=status_filter)

        priority = request.query_params.get('priority')
        if priority:
            jobs_qs = jobs_qs.filter(priority=priority)

        assigned = request.query_params.get('assigned_to')
        if assigned:
            jobs_qs = jobs_qs.filter(assigned_to__id=assigned)

        search = request.query_params.get('search')
        if search:
            jobs_qs = jobs_qs.filter(
                Q(job_id__icontains=search) |
                Q(job_name__icontains=search) |
                Q(client__name__icontains=search)
            )

        date_param = request.query_params.get('date')
        parsed_date = None
        if date_param:
            try:
                parsed_date = date_type.fromisoformat(date_param)
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        entries = []
        for job in jobs_qs.order_by('-created_at'):
            notes = list(job.notes.all())
            if parsed_date:
                notes = [n for n in notes if n.scheduled_datetime and n.scheduled_datetime.date() == parsed_date]
            notes_sorted = sorted(
                [n for n in notes if n.scheduled_datetime is not None],
                key=lambda n: n.scheduled_datetime
            ) + [n for n in notes if n.scheduled_datetime is None]
            if notes_sorted:
                for note in notes_sorted:
                    entries.append(_build_note_job_entry(note, job))
            elif not parsed_date:
                entries.append(_build_job_entry_no_note(job))

        return _paginate(entries, request, JobListSerializer)


class AdminJobListUniqueView(APIView):
    """Admin/manager sees all jobs — one entry per Job (for dropdowns / deduplicated lists)."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['jobs'],
        summary="List all jobs — one row per job (deduplicated)",
        parameters=[
            OpenApiParameter('status', str, description='Filter by job status'),
            OpenApiParameter('priority', str, description='Filter by priority'),
            OpenApiParameter('assigned_to', str, description='Filter by employee UUID'),
            OpenApiParameter('search', str, description='Search by job ID, name, client, or insured address'),
        ]
    )
    def get(self, request):
        jobs_qs = _job_base_qs()

        status_filter = request.query_params.get('status')
        if status_filter:
            jobs_qs = jobs_qs.filter(status=status_filter)

        priority = request.query_params.get('priority')
        if priority:
            jobs_qs = jobs_qs.filter(priority=priority)

        assigned = request.query_params.get('assigned_to')
        if assigned:
            jobs_qs = jobs_qs.filter(assigned_to__id=assigned)

        search = request.query_params.get('search')
        if search:
            jobs_qs = jobs_qs.filter(
                Q(job_id__icontains=search) |
                Q(job_name__icontains=search) |
                Q(client__name__icontains=search) |
                Q(insured_address__icontains=search)
            )

        entries = []
        for job in jobs_qs.order_by('-created_at'):
            notes = sorted(
                [n for n in job.notes.all() if n.scheduled_datetime],
                key=lambda n: n.scheduled_datetime
            )
            if notes:
                entries.append(_build_note_job_entry(notes[0], job))
            else:
                entries.append(_build_job_entry_no_note(job))

        return _paginate(entries, request, JobListSerializer)


class AdminJobDetailView(RetrieveAPIView):
    """Admin/manager retrieves full job detail."""
    permission_classes = [IsAdminOrManager]
    serializer_class = JobDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return Job.objects.prefetch_related('notes__staff', 'notes__tasks')

    @extend_schema(tags=['jobs'], summary="Retrieve job detail (admin/manager)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminJobCreateView(APIView):
    """Admin creates a new job."""
    permission_classes = [IsAdmin]
    serializer_class = JobWriteSerializer

    @extend_schema(
        tags=['jobs'],
        summary="Create job",
        request=JobWriteSerializer,
        responses={201: JobDetailSerializer}
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        job = serializer.save()

        _log_activity(job, ActivityType.JOB_CREATED, request.user, "Job created")
        if job.assigned_to:
            _log_activity(
                job, ActivityType.JOB_ASSIGNED, request.user,
                f"Assigned to {job.assigned_to.full_name}"
            )
            try:
                from notifications.services import NotificationTemplates
                NotificationTemplates.job_assigned(job.assigned_to, job)
            except Exception:
                pass

        return Response(
            {'message': 'Job created.', 'data': JobDetailSerializer(job).data},
            status=status.HTTP_201_CREATED
        )


class AdminJobUpdateView(APIView):
    """Admin updates or deletes a job."""
    permission_classes = [IsAdmin]

    def get_object(self, id):
        return get_object_or_404(Job, id=id)

    @extend_schema(
        tags=['jobs'], summary="Update job",
        request=JobWriteSerializer, responses={200: JobDetailSerializer}
    )
    def patch(self, request, id):
        job = self.get_object(id)
        serializer = JobWriteSerializer(
            job, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        _log_activity(job, ActivityType.STATUS_CHANGED, request.user, "Job updated by admin")

        try:
            from notifications.services import NotificationTemplates
            if job.assigned_to:
                NotificationTemplates.job_updated(job.assigned_to, job)
        except Exception:
            pass

        return Response(
            {'message': 'Job updated.', 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK
        )

    @extend_schema(tags=['jobs'], summary="Delete job", responses={204: None})
    def delete(self, request, id):
        job = self.get_object(id)
        job.delete()
        return Response({'message': 'Job deleted.'}, status=status.HTTP_204_NO_CONTENT)


class AdminJobStatusUpdateView(APIView):
    """
    PATCH /api/jobs/{id}/admin-status/
    Admin forces a job to any status directly.
    """
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['jobs'],
        summary="Admin — force update job status",
        request=AdminJobStatusUpdateSerializer,
        responses={200: JobDetailSerializer},
    )
    def patch(self, request, id):
        job = get_object_or_404(Job, id=id)
        serializer = AdminJobStatusUpdateSerializer(
            job,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        job = serializer.save()

        try:
            from notifications.services import NotificationTemplates
            if job.assigned_to:
                NotificationTemplates.job_updated(job.assigned_to, job)
        except Exception:
            pass

        return Response(
            {'message': f'Job status updated to {job.status}.', 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK
        )


class JobScheduleView(APIView):
    """Deprecated — scheduling is now done through Notes (PATCH /api/notes/{id}/)."""
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['jobs'],
        summary="[Deprecated] Reschedule job — use PATCH /api/notes/{id}/ instead",
        deprecated=True,
        responses={410: None}
    )
    def patch(self, request, id):
        return Response(
            {'detail': 'This endpoint is deprecated. Schedule jobs via PATCH /api/notes/{id}/.'},
            status=status.HTTP_410_GONE
        )


# ==================== EMPLOYEE JOB VIEWS ====================

class EmployeeJobListView(APIView):
    """Employee sees jobs — one entry per Note slot where they are staff, plus jobs assigned to them."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs'],
        summary="Employee — list my jobs (Note-based)",
        parameters=[
            OpenApiParameter('filter', str, description='today | upcoming | completed | active'),
        ]
    )
    def get(self, request):
        from notes.models import Note as NoteModel
        from datetime import date as date_type

        user = request.user
        today = timezone.now().date()
        filter_type = request.query_params.get('filter')

        if user.is_superuser or user.is_staff:
            jobs_qs = _job_base_qs()
            notes_qs = NoteModel.objects.select_related(
                'job', 'job__client', 'job__assigned_to',
                'job__vehicle', 'job__assigned_to__user_color'
            ).prefetch_related('job__safety_forms').filter(job__isnull=False)
        else:
            jobs_qs = _job_base_qs().filter(Q(assigned_to=user) | Q(notes__staff=user)).distinct()
            notes_qs = NoteModel.objects.select_related(
                'job', 'job__client', 'job__assigned_to',
                'job__vehicle', 'job__assigned_to__user_color'
            ).prefetch_related('job__safety_forms').filter(
                Q(staff=user) | Q(job__assigned_to=user),
                job__isnull=False
            ).distinct()

        if filter_type == 'today':
            notes_qs = notes_qs.filter(
                scheduled_datetime__date=today
            ).exclude(job__status=JobStatus.COMPLETED)
        elif filter_type == 'upcoming':
            notes_qs = notes_qs.filter(
                scheduled_datetime__date__gt=today
            ).exclude(job__status=JobStatus.COMPLETED)
        elif filter_type == 'completed':
            notes_qs = notes_qs.filter(job__status=JobStatus.COMPLETED)
        elif filter_type == 'active':
            notes_qs = notes_qs.filter(job__status=JobStatus.IN_PROGRESS)

        entries = []
        seen_job_ids = set()
        for note in notes_qs.order_by('scheduled_datetime'):
            job = note.job
            seen_job_ids.add(job.id)
            entries.append(_build_note_job_entry(note, job))

        # Include jobs with no matching notes (only when not filtering by date-based criteria)
        if filter_type not in ('today', 'upcoming'):
            no_note_qs = jobs_qs.exclude(id__in=seen_job_ids)
            if filter_type == 'completed':
                no_note_qs = no_note_qs.filter(status=JobStatus.COMPLETED)
            elif filter_type == 'active':
                no_note_qs = no_note_qs.filter(status=JobStatus.IN_PROGRESS)
            for job in no_note_qs.order_by('-created_at'):
                entries.append(_build_job_entry_no_note(job))

        return _paginate(entries, request, JobListSerializer)


class EmployeeJobDetailView(RetrieveAPIView):
    """Employee retrieves their assigned job detail."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = JobDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return Job.objects.prefetch_related('notes__staff', 'notes__tasks')
        return Job.objects.filter(
            Q(assigned_to=user) | Q(notes__staff=user)
        ).distinct().prefetch_related('notes__staff', 'notes__tasks')

    @extend_schema(tags=['jobs'], summary="Employee — retrieve job detail")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class JobStatusUpdateView(APIView):
    """Employee updates job status (start job, complete job)."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs'],
        summary="Update job status",
        request=JobStatusUpdateSerializer,
        responses={200: JobDetailSerializer}
    )
    def patch(self, request, id):
        job = get_object_or_404(Job, id=id)
        serializer = JobStatusUpdateSerializer(
            job, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        job = serializer.save()
        return Response(
            {'message': 'Job status updated.', 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK
        )


# ==================== ATTACHMENTS ====================

class JobAttachmentUploadView(APIView):
    """Upload attachments to a job."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=['jobs'], summary="Upload job attachment", request=JobAttachmentSerializer)
    def post(self, request, id):
        job = get_object_or_404(Job, id=id)
        files = request.FILES.getlist('files')
        if not files:
            return Response({'error': 'No files provided.'}, status=status.HTTP_400_BAD_REQUEST)

        created = []
        for f in files:
            attachment = JobAttachment.objects.create(
                job=job, file=f, uploaded_by=request.user
            )
            created.append(JobAttachmentSerializer(attachment).data)

        _log_activity(job, ActivityType.FILE_UPLOADED, request.user,
                      f"{len(files)} file(s) uploaded")
        return Response(
            {'message': 'Files uploaded.', 'data': created},
            status=status.HTTP_201_CREATED
        )


class JobAttachmentDeleteView(APIView):
    """Delete a specific attachment."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(tags=['jobs'], summary="Delete job attachment")
    def delete(self, request, id, attachment_id):
        attachment = get_object_or_404(JobAttachment, id=attachment_id, job__id=id)
        attachment.delete()
        return Response({'message': 'Attachment deleted.'}, status=status.HTTP_204_NO_CONTENT)


# ==================== LINE ITEMS ====================

class JobLineItemView(APIView):
    """Admin manages line items for job scope."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(tags=['jobs'], summary="Add line item", request=JobLineItemSerializer)
    def post(self, request, id):
        job = get_object_or_404(Job, id=id)
        serializer = JobLineItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save(job=job)
        return Response(
            {'message': 'Line item added.', 'data': JobLineItemSerializer(item).data},
            status=status.HTTP_201_CREATED
        )


class JobLineItemDetailView(APIView):
    """Update or delete a specific line item."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(tags=['jobs'], summary="Update line item", request=JobLineItemSerializer)
    def patch(self, request, id, item_id):
        item = get_object_or_404(JobLineItem, id=item_id, job__id=id)
        serializer = JobLineItemSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response({'data': JobLineItemSerializer(item).data})

    @extend_schema(tags=['jobs'], summary="Delete line item")
    def delete(self, request, id, item_id):
        item = get_object_or_404(JobLineItem, id=item_id, job__id=id)
        item.delete()
        return Response({'message': 'Line item deleted.'}, status=status.HTTP_204_NO_CONTENT)


# ==================== JOB TASKS ====================

class JobTasksView(APIView):
    """GET /api/jobs/{id}/tasks/ — all tasks linked to Notes on this job."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(tags=['jobs'], summary="List tasks for a job")
    def get(self, request, id):
        from notes.models import Task as NoteTask
        from notes.serializers import TaskSerializer

        job = get_object_or_404(Job, id=id)
        tasks = NoteTask.objects.filter(
            notes__job=job
        ).distinct().select_related('staff', 'created_by').order_by('-created_at')

        return _paginate(tasks, request, TaskSerializer)



# ==================== ADMIN NOTES + TASKS OVERVIEW ====================

class AdminJobNotesAndTasksView(APIView):
    """
    GET /api/jobs/<uuid:id>/overview/
    Admin-only. Returns all Note schedule slots and every Task linked to
    those notes for the given job, in a single structured response.

    Response shape:
    {
        "id": "<job-uuid>",
        "job_id": "JB-1023",
        "job_name": "...",
        "status": "...",
        "priority": "...",
        "notes_count": 3,
        "tasks_count": 5,
        "notes": [
            {
                "note_id": "...",
                "title": "...",
                "description": "...",
                "scheduled_datetime": "...",
                "end_time": "...",
                "staff": [ { "id", "full_name", "email", "profile_picture" } ],
                "tasks": [ { "id", "name", "description", "due_date",
                             "estimated_cost", "staff", "created_by_name",
                             "created_at", "updated_at" } ],
                "created_by_name": "...",
                "created_at": "...",
                "updated_at": "..."
            }
        ],
        "task_summary": [
            # flat, de-duplicated list of every Task across all notes
            { "id", "name", "description", ... }
        ]
    }
    """
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['jobs'],
        summary="Admin — notes & tasks overview for a job",
        responses={200: AdminJobNotesAndTasksSerializer},
    )
    def get(self, request, id):
        from notes.models import Note as NoteModel, Task as NoteTask

        job = get_object_or_404(
            Job.objects.select_related('client', 'assigned_to', 'vehicle'),
            id=id,
        )

        notes = (
            NoteModel.objects
            .filter(job=job)
            .prefetch_related('staff', 'tasks__staff', 'tasks__created_by', 'created_by')
            .order_by('scheduled_datetime')
        )

        # Flat, de-duplicated task list across all notes for this job
        tasks_qs = (
            NoteTask.objects
            .filter(notes__job=job)
            .distinct()
            .select_related('staff', 'created_by')
        )

        payload = {
            'id': job.id,
            'job_id': job.job_id,
            'job_name': job.job_name,
            'status': job.status,
            'priority': job.priority,
            'notes_count': notes.count(),
            'tasks_count': tasks_qs.count(),
            'notes': notes,
            'task_summary': tasks_qs,
        }

        serializer = AdminJobNotesAndTasksSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ==================== JOB NOTES (chat thread) ====================

class JobNoteListView(APIView):
    """GET /api/jobs/{id}/notes/ — list all chat notes for a job."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-notes'],
        summary="List job notes",
        responses={200: JobNoteSerializer(many=True)},
    )
    def get(self, request, id):
        job = self._get_job(request, id)
        notes = JobNote.objects.filter(job=job).select_related('sender')
        serializer = JobNoteSerializer(notes, many=True, context={'request': request})
        return Response({
            'job_id': job.job_id,
            'count': len(serializer.data),
            'notes': serializer.data,
        }, status=status.HTTP_200_OK)

    def _get_job(self, request, id):
        user = request.user
        if user.is_superuser or user.is_staff:
            return get_object_or_404(Job, id=id)
        return get_object_or_404(
            Job.objects.filter(Q(assigned_to=user) | Q(notes__staff=user)).distinct(),
            id=id
        )


class JobNoteSendView(APIView):
    """POST /api/jobs/{id}/notes/send/ — send a chat note on a job."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-notes'],
        summary="Send job note",
        request=JobNoteCreateSerializer,
        responses={201: JobNoteSerializer},
    )
    def post(self, request, id):
        user = request.user
        if user.is_superuser or user.is_staff:
            job = get_object_or_404(Job, id=id)
        else:
            job = get_object_or_404(
                Job.objects.filter(Q(assigned_to=user) | Q(notes__staff=user)).distinct(),
                id=id
            )

        serializer = JobNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        note = JobNote.objects.create(
            job=job,
            sender=request.user,
            message=serializer.validated_data['message']
        )

        _log_activity(job, ActivityType.NOTE_ADDED, request.user,
                      f"Note added by {request.user.full_name}")

        return Response(
            JobNoteSerializer(note, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class JobNoteDeleteView(APIView):
    """DELETE /api/jobs/{id}/notes/{note_id}/ — delete a chat note."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(tags=['jobs-notes'], summary="Delete a job note", responses={204: None})
    def delete(self, request, id, note_id):
        note = get_object_or_404(JobNote, id=note_id, job__id=id)
        user = request.user

        if not (user.is_superuser or user.is_staff):
            if note.sender != user:
                return Response(
                    {'error': 'You can only delete your own notes.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        note.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== ACTIVITY LOG ====================

class JobActivityListView(ListAPIView):
    """Full activity timeline for a job."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = JobActivitySerializer

    def get_queryset(self):
        return JobActivity.objects.filter(
            job__id=self.kwargs['id']
        ).order_by('created_at')

    @extend_schema(tags=['jobs'], summary="Job activity timeline")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==================== EMPLOYEE JOB LIST VIEWS ====================

class EmployeeMyJobsView(APIView):
    """GET — employee's own jobs split into today / upcoming / completed."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="My jobs — today / upcoming / completed",
        responses={200: EmployeeJobListResponseSerializer}
    )
    def get(self, request):
        from notes.models import Note as NoteModel

        user = request.user
        today = timezone.now().date()

        notes_qs = NoteModel.objects.select_related(
            'job', 'job__client', 'job__assigned_to',
            'job__vehicle', 'job__assigned_to__user_color'
        ).prefetch_related('job__safety_forms').filter(
            Q(staff=user) | Q(job__assigned_to=user),
            job__isnull=False
        ).distinct()

        today_notes = notes_qs.filter(
            scheduled_datetime__date=today
        ).exclude(job__status=JobStatus.COMPLETED).order_by('scheduled_datetime')

        upcoming_notes = notes_qs.filter(
            scheduled_datetime__date__gt=today
        ).exclude(job__status=JobStatus.COMPLETED).order_by('scheduled_datetime')

        today_entries = [_build_note_job_entry(n, n.job) for n in today_notes]
        upcoming_entries = [_build_note_job_entry(n, n.job) for n in upcoming_notes]

        # Completed: all jobs (with or without notes) accessible to user
        completed_jobs = _job_base_qs().filter(
            Q(assigned_to=user) | Q(notes__staff=user),
            status=JobStatus.COMPLETED
        ).distinct().order_by('-created_at')
        completed_entries = [_build_job_entry_no_note(j) for j in completed_jobs]

        return Response({
            'today': JobMinimalSerializer(today_entries, many=True).data,
            'upcoming': JobMinimalSerializer(upcoming_entries, many=True).data,
            'completed': JobMinimalSerializer(completed_entries, many=True).data,
        }, status=status.HTTP_200_OK)


class EmployeeCalendarJobsView(APIView):
    """GET — employee's jobs for calendar view: today / tomorrow / this_week."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="My jobs — calendar view (today / tomorrow / this week)",
        responses={200: EmployeeCalendarJobsSerializer}
    )
    def get(self, request):
        from notes.models import Note as NoteModel

        user = request.user
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        start_of_week = today - timedelta(days=today.weekday())

        week_end = start_of_week + timedelta(days=6)

        notes_qs = NoteModel.objects.select_related(
            'job', 'job__client', 'job__assigned_to',
            'job__vehicle', 'job__assigned_to__user_color'
        ).prefetch_related('job__safety_forms').filter(
            Q(staff=user) | Q(job__assigned_to=user),
            job__isnull=False,
            scheduled_datetime__date__gte=start_of_week,
            scheduled_datetime__date__lte=week_end,
        ).distinct().order_by('scheduled_datetime')

        all_notes = list(notes_qs)

        def notes_for_date(d):
            return [_build_note_job_entry(n, n.job) for n in all_notes if n.scheduled_datetime.date() == d]

        today_entries = notes_for_date(today)
        tomorrow_entries = notes_for_date(tomorrow)

        this_week = {}
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_name = day.strftime('%A').lower()
            this_week[day_name] = JobMinimalSerializer(notes_for_date(day), many=True).data

        return Response({
            'today': JobMinimalSerializer(today_entries, many=True).data,
            'tomorrow': JobMinimalSerializer(tomorrow_entries, many=True).data,
            'this_week': this_week,
        }, status=status.HTTP_200_OK)


class EmployeeJobsByDateView(APIView):
    """GET /api/jobs/employee/jobs-by-date/ — employee's jobs for a specific date."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="My jobs by date",
        parameters=[
            OpenApiParameter('date', str, required=False, description='Filter date YYYY-MM-DD'),
        ],
        responses={200: JobMinimalSerializer(many=True)},
    )
    def get(self, request):
        from notes.models import Note as NoteModel
        from datetime import date as date_type

        user = request.user

        if user.is_superuser or user.is_staff:
            notes_qs = NoteModel.objects.select_related(
                'job', 'job__client', 'job__assigned_to',
                'job__vehicle', 'job__assigned_to__user_color'
            ).prefetch_related('job__safety_forms').filter(job__isnull=False)
        else:
            notes_qs = NoteModel.objects.select_related(
                'job', 'job__client', 'job__assigned_to',
                'job__vehicle', 'job__assigned_to__user_color'
            ).prefetch_related('job__safety_forms').filter(
                Q(staff=user) | Q(job__assigned_to=user),
                job__isnull=False
            ).distinct()

        date_param = request.query_params.get('date')
        if date_param:
            try:
                parsed = date_type.fromisoformat(date_param)
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD e.g. 2026-03-18'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            notes_qs = notes_qs.filter(scheduled_datetime__date=parsed)

        entries = [
            _build_note_job_entry(n, n.job)
            for n in notes_qs.order_by('scheduled_datetime')
        ]
        return Response(
            JobMinimalSerializer(entries, many=True, context={'request': request}).data,
            status=status.HTTP_200_OK
        )


class EmployeeJobDetailByIdView(RetrieveAPIView):
    """Full job detail for employee by job UUID."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = EmployeeJobDetailSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return Job.objects.all()
        return Job.objects.filter(
            Q(assigned_to=user) | Q(notes__staff=user)
        ).distinct()

    def get_object(self):
        queryset = self.get_queryset()
        obj = get_object_or_404(
            queryset.select_related(
                'client', 'vehicle', 'assigned_to'
            ).prefetch_related(
                'attachments', 'safety_forms', 'job_reports', 'notes'
            ),
            id=self.kwargs['id']
        )
        return obj

    @extend_schema(
        tags=['jobs-employee'],
        summary="Job detail (employee)",
        description="Full job detail including client info, vehicle, attachments, and attached reports."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==================== JOB STATUS ACTIONS ====================

class EmployeeStartJobView(APIView):
    """POST — Employee presses 'Start Job'. PENDING → IN_PROGRESS."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="Start job",
        responses={200: EmployeeJobDetailSerializer}
    )
    def post(self, request, id):
        user = request.user
        job = get_object_or_404(
            Job.objects.filter(Q(assigned_to=user) | Q(notes__staff=user)).distinct(),
            id=id
        )

        if job.status == JobStatus.IN_PROGRESS:
            return Response({'message': 'Job is already in progress.'}, status=status.HTTP_200_OK)
        if job.status == JobStatus.COMPLETED:
            return Response({'error': 'Job is already completed.'}, status=status.HTTP_400_BAD_REQUEST)
        if job.status not in [JobStatus.PENDING, JobStatus.OVERDUE, JobStatus.SCHEDULED]:
            return Response(
                {'error': f'Cannot start a job with status "{job.status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        job.status = JobStatus.IN_PROGRESS
        job.save()

        _log_activity(job, ActivityType.JOB_STARTED, request.user, "Job started by employee")

        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.job_started(job)
        except Exception:
            pass

        return Response(
            {
                'message': 'Job started.',
                'data': EmployeeJobDetailSerializer(job, context={'request': request}).data
            },
            status=status.HTTP_200_OK
        )


class EmployeeCompleteJobView(APIView):
    """POST — Employee presses 'Complete Job'. IN_PROGRESS/OVERDUE → COMPLETED."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="Complete job",
        responses={200: EmployeeJobDetailSerializer}
    )
    def post(self, request, id):
        user = request.user
        job = get_object_or_404(
            Job.objects.filter(Q(assigned_to=user) | Q(notes__staff=user)).distinct(),
            id=id
        )

        if job.status == JobStatus.COMPLETED:
            return Response({'message': 'Job is already completed.'}, status=status.HTTP_200_OK)
        if job.status not in [JobStatus.IN_PROGRESS, JobStatus.OVERDUE]:
            return Response(
                {'error': f'Cannot complete a job with status "{job.status}". Please start it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        job.status = JobStatus.COMPLETED
        job.save()

        _log_activity(job, ActivityType.JOB_COMPLETED, request.user, "Job completed by employee")

        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.job_completed(job)
        except Exception:
            pass

        return Response(
            {
                'message': 'Job completed successfully.',
                'data': EmployeeJobDetailSerializer(job, context={'request': request}).data
            },
            status=status.HTTP_200_OK
        )


# ==================== ATTACHMENT DOWNLOAD ====================

class EmployeeJobAttachmentDownloadView(APIView):
    """GET — Employee downloads a specific attachment from their assigned job."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(tags=['jobs-employee'], summary="Download job attachment")
    def get(self, request, id, attachment_id):
        user = request.user
        if user.is_superuser or user.is_staff:
            job = get_object_or_404(Job, id=id)
        else:
            job = get_object_or_404(
                Job.objects.filter(Q(assigned_to=user) | Q(notes__staff=user)).distinct(),
                id=id
            )

        attachment = get_object_or_404(JobAttachment, id=attachment_id, job=job)

        try:
            filename = attachment.file_name or attachment.file.name.split('/')[-1]
            return FileResponse(
                attachment.file.open('rb'),
                as_attachment=True,
                filename=filename
            )
        except FileNotFoundError:
            return Response({'error': 'File not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== RECENT ACTIVITY ====================

class RecentActivityView(APIView):
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['jobs'],
        summary="Recent job activity feed (dashboard)",
        responses={200: RecentActivitySerializer(many=True)}
    )
    def get(self, request):
        activities = (
            JobActivity.objects
            .select_related('job', 'actor')
            .order_by('-created_at')[:5]
        )
        return Response(RecentActivitySerializer(activities, many=True).data)


# ==================== EMPLOYEE VEHICLES ====================

class EmployeeVehicleListView(APIView):
    """
    GET /api/jobs/employee/my-vehicles/
    Returns unique vehicles from the requesting employee's accessible jobs.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="My vehicles",
    )
    def get(self, request):
        from fleets.models import Vehicle as VehicleModel

        user = request.user

        if user.is_superuser or user.is_staff:
            jobs_qs = Job.objects.select_related('vehicle').exclude(vehicle__isnull=True)
        else:
            jobs_qs = Job.objects.filter(
                Q(assigned_to=user) | Q(notes__staff=user)
            ).distinct().select_related('vehicle').exclude(vehicle__isnull=True)

        vehicle_ids = list(
            jobs_qs.values_list('vehicle_id', flat=True).distinct()
        )

        vehicles = VehicleModel.objects.filter(
            id__in=vehicle_ids
        ).prefetch_related('inspections').order_by('name')

        serializer = EmployeeVehicleSerializer(
            vehicles, many=True, context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)
