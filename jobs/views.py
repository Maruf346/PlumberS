from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter
# import datetime
from datetime import timedelta
from django.http import FileResponse

from .models import (
    Job, JobAttachment, JobLineItem, JobActivity,
    JobStatus, JobPriority, ActivityType,
    # JobPhoto,   # commented out
    # JobTask,    # commented out
    JobNote, 
)
from .serializers import (
    AdminJobStatusUpdateSerializer, EmployeeVehicleSerializer, JobListSerializer, JobDetailSerializer, JobWriteSerializer,
    JobScheduleSerializer, JobStatusUpdateSerializer, JobDashboardSerializer,
    JobAttachmentSerializer, JobLineItemSerializer, JobActivitySerializer,
    JobMinimalSerializer, EmployeeJobDetailSerializer,
    EmployeeJobListResponseSerializer, EmployeeCalendarJobsSerializer, RecentActivitySerializer,
    # JobPhotoSerializer,      # commented out
    # JobTaskSerializer,       # commented out
    JobNoteSerializer, 
    JobNoteCreateSerializer,
)
from user.permissions import IsAdmin, IsAdminOrManager, IsAdminOrManagerOrEmployee


def _log_activity(job, activity_type, actor, description=''):
    JobActivity.objects.create(
        job=job,
        activity_type=activity_type,
        actor=actor,
        description=description
    )


# ==================== DASHBOARD ====================

class JobDashboardView(APIView):
    """Admin/manager summary counts."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(tags=['jobs'], summary="Job dashboard summary")
    def get(self, request):
        now = timezone.now()
        today = now.date()

        # Build range using timedelta — no make_aware needed
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        jobs = Job.objects.all()

        active = jobs.filter(status=JobStatus.IN_PROGRESS).count()
        jobs_today = jobs.filter(
            scheduled_datetime__gte=today_start,
            scheduled_datetime__lte=today_end
        ).count()
        pending = jobs.filter(status=JobStatus.PENDING).count()
        completed = jobs.filter(status=JobStatus.COMPLETED).count()
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
            'pending_jobs': pending,
            'completed_jobs': completed,
            'overdue_jobs': overdue,
            'pending_safety_forms': pending_safety,
            'fleet_issues': fleet_issues,
        }
        return Response(JobDashboardSerializer(data).data)


# ==================== JOB CRUD (ADMIN) ====================

class AdminJobListView(ListAPIView):
    """Admin/manager sees all jobs with filtering."""
    permission_classes = [IsAdminOrManager]
    serializer_class = JobListSerializer

    def get_queryset(self):
        qs = Job.objects.select_related(
            'client', 'assigned_to', 'vehicle'
        ).prefetch_related('safety_forms')

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        priority = self.request.query_params.get('priority')
        if priority:
            qs = qs.filter(priority=priority)

        assigned = self.request.query_params.get('assigned_to')
        if assigned:
            qs = qs.filter(assigned_to__id=assigned)

        date_filter = self.request.query_params.get('date')
        if date_filter:
            qs = qs.filter(scheduled_datetime__date=date_filter)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(job_id__icontains=search) |
                Q(job_name__icontains=search) |
                Q(client__name__icontains=search)
            )
        return qs.order_by('-created_at')

    @extend_schema(
        tags=['jobs'],
        summary="List all jobs (admin/manager)",
        parameters=[
            OpenApiParameter('status', str, description='Filter by job status'),
            OpenApiParameter('priority', str, description='Filter by priority'),
            OpenApiParameter('assigned_to', str, description='Filter by employee UUID'),
            OpenApiParameter('date', str, description='Filter by scheduled date YYYY-MM-DD'),
            OpenApiParameter('search', str, description='Search by job ID, name, or client'),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminJobDetailView(RetrieveAPIView):
    """Admin/manager retrieves full job detail."""
    permission_classes = [IsAdminOrManager]
    serializer_class = JobDetailSerializer
    queryset = Job.objects.all()
    lookup_field = 'id'

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
            # Notify assigned employee
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
        
        # Notify assigned employee that their job was updated
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
    No transition rules — full control.
    """
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['jobs'],
        summary="Admin — force update job status",
        description=(
            "Allows admin or manager to set a job to any status directly. "
            "No transition restrictions. Logs the change to the activity timeline."
        ),
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

        # Notify assigned employee if they exist
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
    """Dedicated for drag-and-drop calendar rescheduling."""
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['jobs'],
        summary="Reschedule job (calendar drag-drop)",
        request=JobScheduleSerializer,
        responses={200: JobDetailSerializer}
    )
    def patch(self, request, id):
        job = get_object_or_404(Job, id=id)
        serializer = JobScheduleSerializer(
            job, data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        job = serializer.save()

        now = timezone.now()

        if job.scheduled_datetime and job.scheduled_datetime <= now:
            # New date is still in the past — mark/keep as OVERDUE immediately
            if job.status != JobStatus.OVERDUE:
                job.pre_overdue_status = job.status
                job.status = JobStatus.OVERDUE
                job.save(update_fields=['status', 'pre_overdue_status'])
                _log_activity(
                    job, ActivityType.STATUS_CHANGED, request.user,
                    "Rescheduled to a past date — marked overdue immediately"
                )
            # If already OVERDUE, nothing changes — just log the reschedule

        elif job.scheduled_datetime and job.scheduled_datetime > now:
            # New date is in the future — restore from OVERDUE
            if job.status == JobStatus.OVERDUE:
                restore_to = job.pre_overdue_status or JobStatus.PENDING
                job.status = restore_to
                job.pre_overdue_status = None
                job.save(update_fields=['status', 'pre_overdue_status'])
                _log_activity(
                    job, ActivityType.STATUS_CHANGED, request.user,
                    f"Status restored to {restore_to} after reschedule to future date"
                )

        # Notify assigned employee
        try:
            from notifications.services import NotificationTemplates
            if job.assigned_to:
                NotificationTemplates.job_rescheduled(job.assigned_to, job)
        except Exception:
            pass

        return Response(
            {'message': 'Job rescheduled.', 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK
        )


# ==================== EMPLOYEE JOB VIEWS ====================

class EmployeeJobListView(ListAPIView):
    """Employee sees only their assigned jobs."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = JobListSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            qs = Job.objects.all()
        else:
            qs = Job.objects.filter(assigned_to=user)

        filter_type = self.request.query_params.get('filter')
        today = timezone.now().date()

        if filter_type == 'today':
            qs = qs.filter(scheduled_datetime__date=today)
        elif filter_type == 'upcoming':
            qs = qs.filter(
                scheduled_datetime__date__gt=today
            ).exclude(status=JobStatus.COMPLETED)
        elif filter_type == 'completed':
            qs = qs.filter(status=JobStatus.COMPLETED)
        elif filter_type == 'active':
            qs = qs.filter(status=JobStatus.IN_PROGRESS)

        return qs.order_by('scheduled_datetime')

    @extend_schema(
        tags=['jobs'],
        summary="Employee — list my jobs",
        parameters=[
            OpenApiParameter('filter', str, description='today | upcoming | completed | active')
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class EmployeeJobDetailView(RetrieveAPIView):
    """Employee retrieves their assigned job detail."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = JobDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return Job.objects.all()
        return Job.objects.filter(assigned_to=user)

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


# ── Job Photo Views — commented out (photos now submitted via reports app) ───
# class JobPhotoUploadView(APIView):
#     permission_classes = [IsAdminOrManagerOrEmployee]
#     parser_classes = [MultiPartParser, FormParser]
#     def post(self, request, id): ...
#
# class JobPhotoDeleteView(APIView):
#     permission_classes = [IsAdminOrManager]
#     def delete(self, request, id, photo_id): ...


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


# ── Job Task Views — commented out (tasks feature deferred) ──────────────────
# class JobTaskView(APIView): ...
# class JobTaskCompleteView(APIView): ...


# ── Job Note Views (chat feature deferred to WebSocket phase) ─
class JobNoteListView(APIView):
    """
    GET  /api/jobs/{id}/notes/
    List all notes for a job, oldest first (natural chat order).

    Access rules:
    - Employee: only their assigned job
    - Admin / Manager: any job
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-notes'],
        summary="List job notes",
        description=(
            "Returns all notes for a job in chronological order. "
            "Each note includes sender_role ('admin'/'manager'/'employee') and "
            "is_mine (bool) so the frontend can render left/right chat bubbles."
        ),
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
        # Employee can only see notes on their own job
        return get_object_or_404(Job, id=id, assigned_to=user)


class JobNoteSendView(APIView):
    """
    POST /api/jobs/{id}/notes/send/
    Send a note on a job.

    Access rules:
    - Employee: only on their assigned job
    - Admin / Manager: any job
    Both sides use the same endpoint.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-notes'],
        summary="Send job note",
        description=(
            "Send a message/note on a job thread. "
            "Both employee and admin/manager use this same endpoint. "
            "Returns the created note so the frontend can append it immediately."
        ),
        request=JobNoteCreateSerializer,
        responses={201: JobNoteSerializer},
    )
    def post(self, request, id):
        # Resolve job with access check
        user = request.user
        if user.is_superuser or user.is_staff:
            job = get_object_or_404(Job, id=id)
        else:
            job = get_object_or_404(Job, id=id, assigned_to=user)

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
    """
    DELETE /api/jobs/{id}/notes/{note_id}/
    Admin/manager can delete any note.
    Employee can only delete their own notes.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-notes'],
        summary="Delete a job note",
        responses={204: None},
    )
    def delete(self, request, id, note_id):
        note = get_object_or_404(JobNote, id=note_id, job__id=id)
        user = request.user

        # Admin/manager can delete anything
        # Employee can only delete their own notes
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
    """
    GET — Returns employee's own jobs split into three lists:
    today, upcoming, completed.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="My jobs — today / upcoming / completed",
        responses={200: EmployeeJobListResponseSerializer}
    )
    def get(self, request):
        user = request.user
        now = timezone.now()
        today = now.date()

        base_qs = Job.objects.filter(
            assigned_to=user
        ).select_related('client', 'vehicle').order_by('scheduled_datetime')

        today_jobs = base_qs.filter(
            scheduled_datetime__date=today
        ).exclude(status=JobStatus.COMPLETED)

        upcoming_jobs = base_qs.filter(
            scheduled_datetime__date__gt=today
        ).exclude(status=JobStatus.COMPLETED)

        completed_jobs = base_qs.filter(
            status=JobStatus.COMPLETED
        ).order_by('-scheduled_datetime')

        return Response({
            'today': JobMinimalSerializer(today_jobs, many=True).data,
            'upcoming': JobMinimalSerializer(upcoming_jobs, many=True).data,
            'completed': JobMinimalSerializer(completed_jobs, many=True).data,
        }, status=status.HTTP_200_OK)


class EmployeeCalendarJobsView(APIView):
    """
    GET — Returns employee's jobs for calendar view:
    today, tomorrow, this_week (per-day dict Mon→Sun).
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="My jobs — calendar view (today / tomorrow / this week)",
        responses={200: EmployeeCalendarJobsSerializer}
    )
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        start_of_week = today - timedelta(days=today.weekday())

        base_qs = Job.objects.filter(
            assigned_to=user
        ).select_related('client', 'vehicle').order_by('scheduled_datetime')

        today_jobs = base_qs.filter(scheduled_datetime__date=today)
        tomorrow_jobs = base_qs.filter(scheduled_datetime__date=tomorrow)

        this_week = {}
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_name = day.strftime('%A').lower()
            day_jobs = base_qs.filter(scheduled_datetime__date=day)
            this_week[day_name] = JobMinimalSerializer(day_jobs, many=True).data

        return Response({
            'today': JobMinimalSerializer(today_jobs, many=True).data,
            'tomorrow': JobMinimalSerializer(tomorrow_jobs, many=True).data,
            'this_week': this_week,
        }, status=status.HTTP_200_OK)


class EmployeeJobsByDateView(APIView):
    """
    GET /api/jobs/employee/jobs-by-date/

    Returns the employee's jobs filtered by a specific date.
    Date param is date only — time part is ignored.

    Query param:
        date=YYYY-MM-DD   e.g. ?date=2026-03-18

    Employee → only their assigned jobs.
    Admin/Manager → all jobs on that date.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="My jobs by date",
        description=(
            "Filter employee jobs by a specific date. "
            "Pass date as YYYY-MM-DD — time part is ignored. "
            "Returns all jobs whose scheduled_datetime falls on that date."
        ),
        parameters=[
            OpenApiParameter(
                'date',
                str,
                required=False,
                description='Filter date in YYYY-MM-DD format. Omit to get all jobs.'
            ),
        ],
        responses={200: JobMinimalSerializer(many=True)},
    )
    def get(self, request):
        user = request.user

        if user.is_superuser or user.is_staff:
            qs = Job.objects.select_related('client', 'vehicle').all()
        else:
            qs = Job.objects.filter(
                assigned_to=user
            ).select_related('client', 'vehicle')

        date_param = request.query_params.get('date')

        if date_param:
            # Validate and parse — date only, time is irrelevant
            from datetime import date as date_type
            try:
                parsed = date_type.fromisoformat(date_param)  # expects YYYY-MM-DD
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD e.g. 2026-03-18'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            qs = qs.filter(scheduled_datetime__date=parsed)

        qs = qs.order_by('scheduled_datetime')
        serializer = JobMinimalSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class EmployeeJobDetailByIdView(RetrieveAPIView):
    """Full job detail for employee by job UUID."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = EmployeeJobDetailSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return Job.objects.all()
        return Job.objects.filter(assigned_to=user)

    def get_object(self):
        queryset = self.get_queryset()
        obj = get_object_or_404(
            queryset.select_related(
                'client', 'vehicle', 'assigned_to'
            ).prefetch_related(
                'attachments', 'safety_forms', 'job_reports'
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
        job = get_object_or_404(Job, id=id, assigned_to=request.user)

        if job.status == JobStatus.IN_PROGRESS:
            return Response({'message': 'Job is already in progress.'}, status=status.HTTP_200_OK)
        if job.status == JobStatus.COMPLETED:
            return Response({'error': 'Job is already completed.'}, status=status.HTTP_400_BAD_REQUEST)
        if job.status not in [JobStatus.PENDING, JobStatus.OVERDUE]:
            return Response(
                {'error': f'Cannot start a job with status "{job.status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if job.status == JobStatus.PENDING:
            job.status = JobStatus.IN_PROGRESS
            job.save()

        _log_activity(job, ActivityType.JOB_STARTED, request.user, "Job started by employee")

        # Notify admins/managers           ← ADD THIS BLOCK
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
        job = get_object_or_404(Job, id=id, assigned_to=request.user)

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

    @extend_schema(
        tags=['jobs-employee'],
        summary="Download job attachment"
    )
    def get(self, request, id, attachment_id):
        if request.user.is_superuser or request.user.is_staff:
            job = get_object_or_404(Job, id=id)
        else:
            job = get_object_or_404(Job, id=id, assigned_to=request.user)

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
        
        
class RecentActivityView(APIView):
    # Last 5 job activities for the admin dashboard card.
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['jobs'],
        summary="Recent job activity feed (dashboard)",
        request=RecentActivitySerializer,
        responses={200: RecentActivitySerializer(many=True)}
    )
    def get(self, request):
        from .serializers import RecentActivitySerializer
        activities = (
            JobActivity.objects
            .select_related('job', 'actor')
            .order_by('-created_at')[:5]
        )
        return Response(RecentActivitySerializer(activities, many=True).data)
    
    
class EmployeeVehicleListView(APIView):
    """
    GET /api/jobs/employee/my-vehicles/
 
    Returns unique vehicles from the requesting employee's assigned jobs.
    If two jobs share the same vehicle it appears only once.
 
    Employee → only vehicles from their own jobs.
    Admin/Manager → all vehicles across all jobs.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
 
    @extend_schema(
        tags=['jobs-employee'],
        summary="My vehicles",
        description=(
            "Returns unique vehicles attached to the employee's assigned jobs. "
            "Fields: id, name, plate, picture, status, next_service, last_inspection_date."
        ),
    )
    def get(self, request):
        from fleets.models import Vehicle as VehicleModel
 
        user = request.user
 
        if user.is_superuser or user.is_staff:
            jobs_qs = Job.objects.select_related('vehicle').exclude(vehicle__isnull=True)
        else:
            jobs_qs = Job.objects.filter(
                assigned_to=user
            ).select_related('vehicle').exclude(vehicle__isnull=True)
 
        # Collect unique vehicle IDs from the jobs
        vehicle_ids = list(
            jobs_qs.values_list('vehicle_id', flat=True).distinct()
        )
 
        # Single query with inspection prefetch — no N+1
        vehicles = VehicleModel.objects.filter(
            id__in=vehicle_ids
        ).prefetch_related('inspections').order_by('name')
 
        serializer = EmployeeVehicleSerializer(
            vehicles, many=True, context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)    
