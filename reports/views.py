from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema

from user.permissions import IsAdmin, IsAdminOrManager, IsAdminOrManagerOrEmployee
from jobs.models import JobActivity, ActivityType
from .models import (
    JobReport, ReportType,
    RoofReportSubmission, ApplianceReportSubmission,
    DrainInspectionSubmission, LeakInspectionSubmission,
    SprayTestSubmission,
)
from .serializers import (
    JobReportListSerializer, ReportTypeChoiceSerializer,
    RoofReportFormSerializer, RoofReportSubmitSerializer, RoofReportReadSerializer,
    ApplianceReportFormSerializer, ApplianceReportSubmitSerializer, ApplianceReportReadSerializer,
    DrainInspectionFormSerializer, DrainInspectionSubmitSerializer, DrainInspectionReadSerializer,
    LeakInspectionFormSerializer, LeakInspectionSubmitSerializer, LeakInspectionReadSerializer,
    SprayTestFormSerializer, SprayTestSubmitSerializer, SprayTestReadSerializer,
)

# Map report_type → (FormSerializer, SubmitSerializer, ReadSerializer, submission_related_name)
REPORT_REGISTRY = {
    ReportType.ROOF: (
        RoofReportFormSerializer,
        RoofReportSubmitSerializer,
        RoofReportReadSerializer,
        'roof_submission',
    ),
    ReportType.APPLIANCE: (
        ApplianceReportFormSerializer,
        ApplianceReportSubmitSerializer,
        ApplianceReportReadSerializer,
        'appliance_submission',
    ),
    ReportType.DRAIN_INSPECTION: (
        DrainInspectionFormSerializer,
        DrainInspectionSubmitSerializer,
        DrainInspectionReadSerializer,
        'drain_submission',
    ),
    ReportType.LEAK_INSPECTION: (
        LeakInspectionFormSerializer,
        LeakInspectionSubmitSerializer,
        LeakInspectionReadSerializer,
        'leak_submission',
    ),
    ReportType.SPRAY_TEST: (
        SprayTestFormSerializer,
        SprayTestSubmitSerializer,
        SprayTestReadSerializer,
        'spray_submission',
    ),
}


def _get_job_report_for_employee(job_report_id, user):
    """
    Fetch JobReport ensuring the requesting employee is assigned to the job.
    Raises 404 if not found or not authorized.
    """
    return get_object_or_404(
        JobReport.objects.select_related('job', 'job__client', 'job__assigned_to'),
        id=job_report_id,
        job__assigned_to=user
    )


def _log_report_submitted(job_report, user):
    """Log REPORT_SUBMITTED activity on the job's activity timeline."""
    JobActivity.objects.create(
        job=job_report.job,
        activity_type=ActivityType.REPORT_SUBMITTED,
        actor=user,
        description=f"{job_report.get_report_type_display()} submitted by {user.full_name}"
    )


# ==================== REPORT TYPE CHOICES ====================

class ReportTypeListView(APIView):
    """
    GET — Returns all available report type choices.
    Used by admin when creating a job to select which report types to attach.
    """
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['reports'],
        summary="Available report types",
        description="Returns all valid report type choices for admin job creation."
    )
    def get(self, request):
        choices = [{'value': c[0], 'label': c[1]} for c in ReportType.choices]
        return Response(choices, status=status.HTTP_200_OK)


# ==================== ADMIN — REPORTS FOR A JOB ====================

class JobReportListView(ListAPIView):
    """
    GET /api/jobs/{job_id}/reports/
    Admin/manager sees all reports attached to a job with submission status.
    Used in the admin job panel to show which reports are pending/submitted.
    """
    permission_classes = [IsAdminOrManager]
    serializer_class = JobReportListSerializer

    def get_queryset(self):
        return JobReport.objects.filter(
            job__id=self.kwargs['job_id']
        ).select_related('submitted_by').order_by('created_at')

    @extend_schema(
        tags=['reports'],
        summary="List reports for a job (admin)",
        description="Returns all report types attached to a job and their submission status."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==================== FORM VIEW (GET — employee loads form) ====================

class ReportFormView(APIView):
    """
    GET /api/reports/{job_report_id}/form/
    Employee loads the report form.
    Returns pre-filled DB fields + available choices + existing submission if already done.
    Permission: only the assigned employee for this job.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['reports'],
        summary="Load report form",
        description=(
            "Returns pre-filled fields (from job/client/employee DB), "
            "available choices for dropdown fields, and existing submission data if already submitted."
        )
    )
    def get(self, request, job_report_id):
        # Employee: must be assigned to the job
        # Admin/manager: can view any
        if request.user.is_superuser or request.user.is_staff:
            job_report = get_object_or_404(
                JobReport.objects.select_related('job', 'job__client', 'job__assigned_to'),
                id=job_report_id
            )
        else:
            job_report = _get_job_report_for_employee(job_report_id, request.user)

        form_serializer_class = REPORT_REGISTRY.get(job_report.report_type, (None,))[0]
        if not form_serializer_class:
            return Response(
                {'error': f'Unknown report type: {job_report.report_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = form_serializer_class(
            job_report,
            context={'request': request}
        )
        return Response({
            'job_report_id': str(job_report.id),
            'report_type': job_report.report_type,
            'report_type_display': job_report.get_report_type_display(),
            'is_submitted': job_report.is_submitted,
            'submitted_at': job_report.submitted_at,
            **serializer.data
        }, status=status.HTTP_200_OK)


# ==================== SUBMIT VIEW (POST — employee submits report) ====================

class ReportSubmitView(APIView):
    """
    POST /api/reports/{job_report_id}/submit/
    Employee submits the report.
    Only the employee assigned to the job can submit.
    Report is locked once submitted — no updates allowed.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=['reports'],
        summary="Submit report",
        description=(
            "Submit a report for a job. "
            "Only the assigned employee can submit. "
            "Locked permanently after submission."
        )
    )
    def post(self, request, job_report_id):
        # Only the assigned employee can submit
        if request.user.is_superuser or request.user.is_staff:
            return Response(
                {'error': 'Only the assigned employee can submit reports.'},
                status=status.HTTP_403_FORBIDDEN
            )

        job_report = _get_job_report_for_employee(job_report_id, request.user)

        if job_report.is_submitted:
            return Response(
                {'error': 'This report has already been submitted and cannot be changed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        submit_serializer_class = REPORT_REGISTRY.get(job_report.report_type, (None, None))[1]
        if not submit_serializer_class:
            return Response(
                {'error': f'Unknown report type: {job_report.report_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = submit_serializer_class(
            data=request.data,
            context={
                'request': request,
                'job_report': job_report,
            }
        )
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()

        # Log to job activity timeline
        _log_report_submitted(job_report, request.user)

        # Notify admins/managers about the new report submission
        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.report_submitted(job_report, request.user)
        except Exception:
            pass

        return Response(
            {
                'message': f'{job_report.get_report_type_display()} submitted successfully.',
                'job_report_id': str(job_report.id),
                'submitted_at': job_report.submitted_at,
            },
            status=status.HTTP_201_CREATED
        )


# ==================== SUBMISSION VIEW (GET — view submitted report) ====================

class ReportSubmissionView(APIView):
    """
    GET /api/reports/{job_report_id}/submission/
    View a submitted report.
    Accessible by: the employee who submitted it + admin/manager.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['reports'],
        summary="View submitted report",
        description="View the full data of a submitted report. Employee (who submitted) + admin/manager only."
    )
    def get(self, request, job_report_id):
        user = request.user

        if user.is_superuser or user.is_staff:
            job_report = get_object_or_404(
                JobReport.objects.select_related('job', 'job__client', 'job__assigned_to'),
                id=job_report_id
            )
        else:
            # Employee: must be assigned to the job
            job_report = _get_job_report_for_employee(job_report_id, user)

        if not job_report.is_submitted:
            return Response(
                {'error': 'This report has not been submitted yet.'},
                status=status.HTTP_404_NOT_FOUND
            )

        read_serializer_class, related_name = (
            REPORT_REGISTRY.get(job_report.report_type, (None, None, None, None))[2],
            REPORT_REGISTRY.get(job_report.report_type, (None, None, None, None))[3],
        )

        if not read_serializer_class:
            return Response(
                {'error': f'Unknown report type: {job_report.report_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            submission = getattr(job_report, related_name)
        except Exception:
            return Response(
                {'error': 'Submission data not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = read_serializer_class(submission, context={'request': request})
        return Response({
            'job_report_id': str(job_report.id),
            'report_type': job_report.report_type,
            'report_type_display': job_report.get_report_type_display(),
            'submitted_by': job_report.submitted_by.full_name if job_report.submitted_by else None,
            'submitted_at': job_report.submitted_at,
            'data': serializer.data,
        }, status=status.HTTP_200_OK)


# ==================== PDF DOWNLOAD VIEW ====================

class ReportDownloadView(APIView):
    """
    GET /api/reports/{job_report_id}/download/
    Admin/manager downloads the submitted report as a PDF.
    """
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['reports'],
        summary="Download report PDF",
        description="Generate and download a submitted report as a PDF. Admin/manager only."
    )
    def get(self, request, job_report_id):
        job_report = get_object_or_404(
            JobReport.objects.select_related(
                'job', 'job__client', 'job__assigned_to', 'submitted_by'
            ),
            id=job_report_id
        )

        if not job_report.is_submitted:
            return Response(
                {'error': 'Cannot generate PDF — report has not been submitted yet.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        related_name = REPORT_REGISTRY.get(job_report.report_type, (None, None, None, None))[3]
        if not related_name:
            return Response(
                {'error': f'Unknown report type: {job_report.report_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            submission = getattr(job_report, related_name)
        except Exception:
            return Response(
                {'error': 'Submission data not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Route to correct PDF generator
        try:
            from .pdf.generator import generate_pdf
            pdf_buffer = generate_pdf(job_report, submission)
        except Exception as e:
            return Response(
                {'error': f'PDF generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        from django.http import FileResponse
        filename = (
            f"{job_report.get_report_type_display().replace(' ', '_')}_"
            f"{job_report.job.job_id}.pdf"
        )
        pdf_buffer.seek(0)
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=filename,
            content_type='application/pdf'
        )