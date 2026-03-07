from httpx import request
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
import datetime

from .models import *
from .serializers import *
from user.permissions import *


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
        from fleets.models import VehicleStatus
        from fleets.models import Vehicle

        today = timezone.now().date()
        jobs = Job.objects.all()

        # Mark overdue
        # for job in jobs.filter(
        #     scheduled_datetime__lt=timezone.now()
        # ).exclude(status=JobStatus.COMPLETED):
        #     job.check_overdue()
        # Celery beat handles overdue marking — no need to loop here
        
        jobs = Job.objects.all()  # re-query after updates

        active = jobs.filter(status=JobStatus.IN_PROGRESS).count()
        jobs_today = jobs.filter(scheduled_datetime__date=today).count()
        pending = jobs.filter(status=JobStatus.PENDING).count()
        completed = jobs.filter(status=JobStatus.COMPLETED).count()
        overdue = jobs.filter(status=JobStatus.OVERDUE).count()

        # Jobs with safety forms not yet submitted (IN_PROGRESS + has safety forms)
        pending_safety = jobs.filter(
            status=JobStatus.IN_PROGRESS
        ).filter(safety_forms__isnull=False).distinct().count()

        # Jobs with fleet issues
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
    """
    Admin/manager sees all jobs.
    Supports filtering by status, priority, assigned employee, date.
    """
    permission_classes = [IsAdminOrManager]
    serializer_class = JobListSerializer

    def get_queryset(self):
        qs = Job.objects.select_related(
            'client', 'assigned_to', 'vehicle'
        ).prefetch_related('tasks', 'safety_forms')

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
            OpenApiParameter('search', str, description='Search by job ID, insured name, client'),
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
            _log_activity(job, ActivityType.JOB_ASSIGNED, request.user,
                          f"Assigned to {job.assigned_to.full_name}")
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
        return Response(
            {'message': 'Job updated.', 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK
        )

    @extend_schema(tags=['jobs'], summary="Delete job", responses={204: None})
    def delete(self, request, id):
        job = self.get_object(id)
        job.delete()
        return Response({'message': 'Job deleted.'}, status=status.HTTP_204_NO_CONTENT)


class JobScheduleView(APIView):
    """
    Dedicated endpoint for drag-and-drop calendar rescheduling.
    PATCH with just scheduled_datetime.
    """
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
        return Response(
            {'message': 'Job rescheduled.', 'data': JobDetailSerializer(job).data},
            status=status.HTTP_200_OK
        )


# ==================== EMPLOYEE JOB VIEWS ====================

class EmployeeJobListView(ListAPIView):
    """
    Employee sees only their assigned jobs.
    Filter: today, upcoming, completed.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = JobListSerializer

    def get_queryset(self):
        user = self.request.user

        # Admin/manager can see all; employee sees only their own
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
            OpenApiParameter(
                'filter', str,
                description='today | upcoming | completed | active'
            )
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


# ==================== ATTACHMENTS & PHOTOS ====================

class JobAttachmentUploadView(APIView):
    """Any staff member can upload attachments to a job."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=['jobs'], summary="Upload job attachment")
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
        return Response({'message': 'Files uploaded.', 'data': created}, status=status.HTTP_201_CREATED)


class JobAttachmentDeleteView(APIView):
    """Delete a specific attachment."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(tags=['jobs'], summary="Delete job attachment")
    def delete(self, request, id, attachment_id):
        attachment = get_object_or_404(JobAttachment, id=attachment_id, job__id=id)
        attachment.delete()
        return Response({'message': 'Attachment deleted.'}, status=status.HTTP_204_NO_CONTENT)


class JobPhotoUploadView(APIView):
    """Employee uploads job completion photos with captions."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=['jobs'], summary="Upload job photo")
    def post(self, request, id):
        job = get_object_or_404(Job, id=id)
        image = request.FILES.get('image')
        caption = request.data.get('caption', '')

        if not image:
            return Response({'error': 'No image provided.'}, status=status.HTTP_400_BAD_REQUEST)

        photo = JobPhoto.objects.create(
            job=job, image=image, caption=caption, uploaded_by=request.user
        )
        _log_activity(job, ActivityType.FILE_UPLOADED, request.user, "Photo uploaded")
        return Response(
            {'message': 'Photo uploaded.', 'data': JobPhotoSerializer(photo).data},
            status=status.HTTP_201_CREATED
        )


class JobPhotoDeleteView(APIView):
    """Delete a specific photo."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(tags=['jobs'], summary="Delete job photo")
    def delete(self, request, id, photo_id):
        photo = get_object_or_404(JobPhoto, id=photo_id, job__id=id)
        photo.delete()
        return Response({'message': 'Photo deleted.'}, status=status.HTTP_204_NO_CONTENT)


# ==================== LINE ITEMS ====================

class JobLineItemView(APIView):
    """Admin manages line items for job scope."""
    permission_classes = [IsAdminOrManager]

    @extend_schema(tags=['jobs'], summary="Add line item")
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

    @extend_schema(tags=['jobs'], summary="Update line item")
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


# ==================== TASKS ====================

class JobTaskView(APIView):
    """Admin adds tasks; employee marks them done."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(tags=['jobs'], summary="Add task to job")
    def post(self, request, id):
        if not (request.user.is_superuser or request.user.is_staff):
            return Response(
                {'error': 'Only admin or manager can add tasks.'},
                status=status.HTTP_403_FORBIDDEN
            )
        job = get_object_or_404(Job, id=id)
        serializer = JobTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save(job=job)
        return Response(
            {'message': 'Task added.', 'data': JobTaskSerializer(task).data},
            status=status.HTTP_201_CREATED
        )


class JobTaskCompleteView(APIView):
    """Employee marks a task as done."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(tags=['jobs'], summary="Mark task as done")
    def post(self, request, id, task_id):
        task = get_object_or_404(JobTask, id=task_id, job__id=id)
        if task.is_done:
            return Response({'message': 'Task already completed.'})
        task.mark_done(request.user)
        _log_activity(
            task.job, ActivityType.TASK_COMPLETED,
            request.user, f"Task '{task.description}' completed"
        )
        return Response(
            {'message': 'Task marked as done.', 'data': JobTaskSerializer(task).data}
        )


# ==================== NOTES (CHAT) ====================

class JobNoteListView(ListAPIView):
    """List all notes/messages for a job."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = JobNoteSerializer

    def get_queryset(self):
        return JobNote.objects.filter(job__id=self.kwargs['id']).order_by('created_at')

    @extend_schema(tags=['jobs'], summary="List job notes/messages")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class JobNoteCreateView(APIView):
    """Send a message in the job thread."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs'], summary="Send job note/message",
        request=JobNoteCreateSerializer, responses={201: JobNoteSerializer}
    )
    def post(self, request, id):
        job = get_object_or_404(Job, id=id)
        serializer = JobNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = JobNote.objects.create(
            job=job,
            sender=request.user,
            message=serializer.validated_data['message']
        )
        _log_activity(job, ActivityType.NOTE_ADDED, request.user, "Note added")
        return Response(
            {'data': JobNoteSerializer(note).data},
            status=status.HTTP_201_CREATED
        )


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
    
    

from datetime import timedelta, date as date_type
from django.utils.timezone import make_aware
from django.utils import timezone


# ==================== EMPLOYEE JOB LIST VIEWS ====================

class EmployeeMyJobsView(APIView):
    """
    GET — Returns employee's own jobs split into three lists:
    today, upcoming, completed.
    Sorted by scheduled_datetime ascending within each group.
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
        ).select_related(
            'client', 'vehicle'
        ).order_by('scheduled_datetime')

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
    today, tomorrow, this_week (remaining days after tomorrow).
    Sorted by scheduled_datetime ascending.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="My jobs — calendar view (today / tomorrow / this week)",
        responses={200: EmployeeCalendarJobsSerializer}
    )
    def get(self, request):
        user = request.user
        now = timezone.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)

        # Week starts Monday (weekday()=0) to Sunday (weekday()=6)
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        end_of_week = start_of_week + timedelta(days=6)          # Sunday

        base_qs = Job.objects.filter(
            assigned_to=user
        ).select_related(
            'client', 'vehicle'
        ).order_by('scheduled_datetime')

        today_jobs = base_qs.filter(scheduled_datetime__date=today)
        tomorrow_jobs = base_qs.filter(scheduled_datetime__date=tomorrow)

        # Build per-day dict for the full week (Mon → Sun)
        this_week = {}
        for i in range(7):
            day = start_of_week + timedelta(days=i)
            day_name = day.strftime('%A').lower()  # monday, tuesday...
            day_jobs = base_qs.filter(scheduled_datetime__date=day)
            this_week[day_name] = JobMinimalSerializer(day_jobs, many=True).data

        return Response({
            'today': JobMinimalSerializer(today_jobs, many=True).data,
            'tomorrow': JobMinimalSerializer(tomorrow_jobs, many=True).data,
            'this_week': this_week,
        }, status=status.HTTP_200_OK)


class EmployeeJobDetailByIdView(RetrieveAPIView):
    """
    GET — Full job detail for employee by job UUID.
    Returns everything needed to render the job detail screen.
    """
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
                'attachments', 'tasks', 'safety_forms'
            ),
            id=self.kwargs['id']
        )
        return obj

    @extend_schema(
        tags=['jobs-employee'],
        summary="Job detail (employee)",
        description="Full job detail including client info, vehicle, attachments, tasks, safety forms."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==================== JOB STATUS ACTIONS ====================

class EmployeeStartJobView(APIView):
    """
    POST — Employee presses 'Start Job' button.
    Transitions: PENDING → IN_PROGRESS, OVERDUE stays OVERDUE.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="Start job",
        responses={200: EmployeeJobDetailSerializer}
    )
    def post(self, request, id):
        job = get_object_or_404(Job, id=id, assigned_to=request.user)

        if job.status == JobStatus.IN_PROGRESS:
            return Response(
                {'message': 'Job is already in progress.'},
                status=status.HTTP_200_OK
            )

        if job.status == JobStatus.COMPLETED:
            return Response(
                {'error': 'Job is already completed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if job.status not in [JobStatus.PENDING, JobStatus.OVERDUE]:
            return Response(
                {'error': f'Cannot start a job with status "{job.status}".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Only PENDING transitions to IN_PROGRESS
        # OVERDUE stays OVERDUE — employee can still work on it
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.IN_PROGRESS
            job.save()

        _log_activity(
            job, ActivityType.JOB_STARTED,
            request.user, "Job started by employee"
        )

        return Response(
            {
                'message': 'Job started.',
                'data': EmployeeJobDetailSerializer(job, context={'request': request}).data
            },
            status=status.HTTP_200_OK
        )


class EmployeeCompleteJobView(APIView):
    """
    POST — Employee presses 'Complete Job' button.
    Transitions: IN_PROGRESS → COMPLETED, OVERDUE → COMPLETED.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="Complete job",
        responses={200: EmployeeJobDetailSerializer}
    )
    def post(self, request, id):
        job = get_object_or_404(Job, id=id, assigned_to=request.user)

        if job.status == JobStatus.COMPLETED:
            return Response(
                {'message': 'Job is already completed.'},
                status=status.HTTP_200_OK
            )

        if job.status not in [JobStatus.IN_PROGRESS, JobStatus.OVERDUE]:
            return Response(
                {'error': f'Cannot complete a job with status "{job.status}". Please start it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        job.status = JobStatus.COMPLETED
        job.save()

        _log_activity(
            job, ActivityType.JOB_COMPLETED,
            request.user, "Job completed by employee"
        )

        return Response(
            {
                'message': 'Job completed successfully.',
                'data': EmployeeJobDetailSerializer(job, context={'request': request}).data
            },
            status=status.HTTP_200_OK
        )


# ==================== ATTACHMENT DOWNLOAD ====================

class EmployeeJobAttachmentDownloadView(APIView):
    """
    GET — Employee downloads a specific attachment from their assigned job.
    Streams the file directly as a response.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['jobs-employee'],
        summary="Download job attachment",
        description="Download a specific file attachment from an assigned job."
    )
    def get(self, request, id, attachment_id):
        # Employees can only download from their own jobs
        # Admin/manager can download from any job
        if request.user.is_superuser or request.user.is_staff:
            job = get_object_or_404(Job, id=id)
        else:
            job = get_object_or_404(Job, id=id, assigned_to=request.user)

        attachment = get_object_or_404(JobAttachment, id=attachment_id, job=job)

        try:
            file = attachment.file
            filename = attachment.file_name or file.name.split('/')[-1]

            from django.http import FileResponse
            response = FileResponse(
                file.open('rb'),
                as_attachment=True,
                filename=filename
            )
            return response

        except FileNotFoundError:
            return Response(
                {'error': 'File not found on server.'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Could not download file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )