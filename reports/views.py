from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import FileResponse
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample

from user.permissions import IsAdmin, IsAdminOrManager, IsAdminOrManagerOrEmployee
from jobs.models import JobActivity, ActivityType
from .models import (
    JobReport, ReportType,
    RoofReportSubmission, ApplianceReportSubmission,
    DrainInspectionSubmission, LeakInspectionSubmission,
    SprayTestSubmission,
)
from .serializers import (
    JobReportListSerializer,
    RoofReportFormSerializer, RoofReportSubmitSerializer, RoofReportReadSerializer,
    ApplianceReportFormSerializer, ApplianceReportSubmitSerializer, ApplianceReportReadSerializer,
    DrainInspectionFormSerializer, DrainInspectionSubmitSerializer, DrainInspectionReadSerializer,
    LeakInspectionFormSerializer, LeakInspectionSubmitSerializer, LeakInspectionReadSerializer,
    SprayTestFormSerializer, SprayTestSubmitSerializer, SprayTestReadSerializer,
    FORM_FIELDS_REGISTRY,
)

# ── Registry: report_type → (FormSerializer, SubmitSerializer, ReadSerializer, related_name)
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


# ==================== SHARED HELPERS ====================

def _get_job_report_for_employee(job_report_id, user):
    return get_object_or_404(
        JobReport.objects.select_related('job', 'job__client', 'job__assigned_to'),
        id=job_report_id,
        job__assigned_to=user
    )


def _log_report_submitted(job_report, user):
    JobActivity.objects.create(
        job=job_report.job,
        activity_type=ActivityType.REPORT_SUBMITTED,
        actor=user,
        description=f"{job_report.get_report_type_display()} submitted by {user.full_name}"
    )


def _handle_submit(request, job_report_id, expected_report_type):
    """
    Shared submit logic used by all 5 typed submit views.
    Validates the job_report belongs to the employee, matches the expected
    report type, is not already submitted, then delegates to the correct
    submit serializer.
    """
    if request.user.is_superuser or request.user.is_staff:
        return Response(
            {'error': 'Only the assigned employee can submit reports.'},
            status=status.HTTP_403_FORBIDDEN
        )

    job_report = _get_job_report_for_employee(job_report_id, request.user)

    # Guard: wrong endpoint for this report type
    if job_report.report_type != expected_report_type:
        return Response(
            {
                'error': (
                    f'This report is of type "{job_report.get_report_type_display()}". '
                    f'Please use the correct submit endpoint.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    if job_report.is_submitted:
        return Response(
            {'error': 'This report has already been submitted and cannot be changed.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    submit_serializer_class = REPORT_REGISTRY[expected_report_type][1]
    serializer = submit_serializer_class(
        data=request.data,
        context={'request': request, 'job_report': job_report}
    )
    serializer.is_valid(raise_exception=True)
    serializer.save()

    _log_report_submitted(job_report, request.user)

    try:
        from notifications.services import NotificationTemplates
        NotificationTemplates.report_submitted(job_report, request.user)
    except Exception:
        pass

    # Refresh from DB so submitted_at is populated
    job_report.refresh_from_db()

    return Response(
        {
            'message': f'{job_report.get_report_type_display()} submitted successfully.',
            'job_report_id': str(job_report.id),
            'submitted_at': job_report.submitted_at,
        },
        status=status.HTTP_201_CREATED
    )


# ==================== REPORT TYPE CHOICES ====================

class ReportTypeListView(APIView):
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
    permission_classes = [IsAdminOrManager]
    serializer_class = JobReportListSerializer

    def get_queryset(self):
        return JobReport.objects.filter(
            job__id=self.kwargs['job_id']
        ).select_related('submitted_by').order_by('created_at')

    @extend_schema(tags=['reports'], summary="List reports for a job (admin)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==================== FORM FIELDS — structural schema ====================

class ReportFormFieldsView(APIView):
    """
    GET /api/reports/{job_report_id}/formfields/
    Returns the complete field list for this specific report type.
    Pure structure — no DB values, no submission data.
    Use this to render the form UI dynamically.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['reports'],
        summary="Report form field schema",
        description=(
            "Returns every field the employee must fill in for this report type. "
            "Each entry has: name, type, required, choices (if select), help_text. "
            "Types: datetime, text, textarea, select, boolean, photo, photos. "
            "No DB data — purely structural. "
            "The submit_url in the response points to the correct typed submit endpoint."
        )
    )
    def get(self, request, job_report_id):
        if request.user.is_superuser or request.user.is_staff:
            job_report = get_object_or_404(JobReport.objects.select_related('job'), id=job_report_id)
        else:
            job_report = _get_job_report_for_employee(job_report_id, request.user)

        fields = FORM_FIELDS_REGISTRY.get(job_report.report_type)
        if fields is None:
            return Response(
                {'error': f'Unknown report type: {job_report.report_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Map report_type to its typed submit URL slug
        submit_slug_map = {
            ReportType.ROOF: 'roof',
            ReportType.APPLIANCE: 'appliance',
            ReportType.DRAIN_INSPECTION: 'drain',
            ReportType.LEAK_INSPECTION: 'leak',
            ReportType.SPRAY_TEST: 'spray',
        }
        slug = submit_slug_map.get(job_report.report_type, '')

        return Response({
            'job_report_id': str(job_report.id),
            'report_type': job_report.report_type,
            'report_type_display': job_report.get_report_type_display(),
            'is_submitted': job_report.is_submitted,
            'submit_url': f'/api/reports/{job_report.id}/submit/{slug}/',
            'fields': fields,
        }, status=status.HTTP_200_OK)


# ==================== FORM VIEW — pre-filled data ====================

class ReportFormView(APIView):
    """
    GET /api/reports/{job_report_id}/form/
    Returns pre-filled DB values + choices + existing submission if already done.
    Unchanged from original.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['reports'],
        summary="Load report form (pre-filled data)",
        description=(
            "Returns pre-filled fields from DB (job, client, employee) and dropdown choices. "
            "Also returns submitted data if report is already submitted. "
            "For field structure/schema use GET /formfields/ instead."
        )
    )
    def get(self, request, job_report_id):
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

        serializer = form_serializer_class(job_report, context={'request': request})
        return Response({
            'job_report_id': str(job_report.id),
            'report_type': job_report.report_type,
            'report_type_display': job_report.get_report_type_display(),
            'is_submitted': job_report.is_submitted,
            'submitted_at': job_report.submitted_at,
            **serializer.data
        }, status=status.HTTP_200_OK)


# ==================== TYPED SUBMIT VIEWS — one per report type ====================

class RoofReportSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['reports'],
        summary="Submit Roof Report",
        description="Submit a Roof Report. Employee only. multipart/form-data.",
        request={
            'multipart/form-data': {
                'type': 'object',
                'required': ['attendance_datetime'],
                'properties': {
                    'attendance_datetime': {'type': 'string', 'format': 'date-time',
                                           'description': 'REQUIRED. ISO 8601 e.g. 2026-03-12T09:30:00'},
                    'discussion_with_insured': {'type': 'string'},
                    'type_of_dwelling': {'type': 'string',
                                        'enum': ['single_story', 'two_story', 'complex']},
                    'resulting_damages': {'type': 'string'},
                    'leak_fixed_by_insured': {'type': 'string', 'enum': ['yes', 'no', 'na']},
                    'type_of_roof': {'type': 'string',
                                    'enum': ['iron', 'tile', 'asbestos', 'poly_sheeting', 'pressed_metal']},
                    'pitch_of_roof': {'type': 'string'},
                    'leak_present': {'type': 'string', 'enum': ['yes', 'no', 'na']},
                    'cause_of_leak_found': {'type': 'string', 'enum': ['yes', 'no', 'na']},
                    'leak_fixed': {'type': 'string', 'enum': ['yes', 'no', 'na']},
                    'works_required': {'type': 'string'},
                    'conclusion': {'type': 'string'},
                    'front_of_dwelling': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                         'description': 'Repeat field for multiple files'},
                    'damage_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                     'description': 'Repeat field for multiple files'},
                    'job_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                  'description': 'Repeat field for multiple files'},
                }
            }
        },
        responses={
            201: OpenApiResponse(description="Roof Report submitted successfully"),
            400: OpenApiResponse(description="Validation error or already submitted"),
            403: OpenApiResponse(description="Admin/manager cannot submit"),
        }
    )
    def post(self, request, job_report_id):
        return _handle_submit(request, job_report_id, ReportType.ROOF)


class ApplianceReportSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['reports'],
        summary="Submit Appliance Report",
        description="Submit an Appliance Report. Employee only. multipart/form-data.",
        request={
            'multipart/form-data': {
                'type': 'object',
                'required': ['attendance_datetime'],
                'properties': {
                    'attendance_datetime': {'type': 'string', 'format': 'date-time',
                                           'description': 'REQUIRED. ISO 8601 e.g. 2026-03-12T09:30:00'},
                    'discussion_with_insured': {'type': 'string'},
                    'appliance_brand': {'type': 'string'},
                    'model_no': {'type': 'string'},
                    'approx_age': {'type': 'string',
                                  'description': "e.g. '5 years', '~10 yrs'"},
                    'conclusion': {'type': 'string'},
                    'front_of_property': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                         'description': 'Repeat field for multiple files'},
                    'job_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                  'description': 'Repeat field for multiple files'},
                }
            }
        },
        responses={
            201: OpenApiResponse(description="Appliance Report submitted successfully"),
            400: OpenApiResponse(description="Validation error or already submitted"),
            403: OpenApiResponse(description="Admin/manager cannot submit"),
        }
    )
    def post(self, request, job_report_id):
        return _handle_submit(request, job_report_id, ReportType.APPLIANCE)


class DrainInspectionSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['reports'],
        summary="Submit Drain Inspection Report",
        description="Submit a Drain Inspection Report. Employee only. multipart/form-data.",
        request={
            'multipart/form-data': {
                'type': 'object',
                'required': ['attendance_datetime'],
                'properties': {
                    'attendance_datetime': {'type': 'string', 'format': 'date-time',
                                           'description': 'REQUIRED. ISO 8601 e.g. 2026-03-12T09:30:00'},
                    'property_construction': {'type': 'string',
                                             'enum': ['brick_veneer', 'double_brick']},
                    'discussion_with_insured': {'type': 'string'},
                    'resultant_damage': {'type': 'string'},
                    'area_of_inspection': {'type': 'string',
                                          'enum': ['consumer_sewer', 'consumer_stormwater']},
                    'pipe_construction': {'type': 'string',
                                         'enum': ['pvc', 'ceramic', 'hdpe', 'galvanised', 'lead']},
                    'conclusion': {'type': 'string'},
                    'front_of_dwelling': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                         'description': 'Repeat field for multiple files'},
                    'damage_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                     'description': 'Repeat field for multiple files'},
                    'job_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                  'description': 'Repeat field for multiple files'},
                }
            }
        },
        responses={
            201: OpenApiResponse(description="Drain Inspection Report submitted successfully"),
            400: OpenApiResponse(description="Validation error or already submitted"),
            403: OpenApiResponse(description="Admin/manager cannot submit"),
        }
    )
    def post(self, request, job_report_id):
        return _handle_submit(request, job_report_id, ReportType.DRAIN_INSPECTION)


class LeakInspectionSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['reports'],
        summary="Submit Leak Inspection Report",
        description="Submit a Leak Inspection Report. Employee only. multipart/form-data.",
        request={
            'multipart/form-data': {
                'type': 'object',
                'required': ['attendance_datetime'],
                'properties': {
                    'attendance_datetime': {'type': 'string', 'format': 'date-time',
                                           'description': 'REQUIRED. ISO 8601 e.g. 2026-03-12T09:30:00'},
                    'property_construction': {'type': 'string',
                                             'enum': ['brick_veneer', 'double_brick']},
                    'discussion_with_site_contact': {'type': 'string'},
                    'resultant_damage': {'type': 'string'},
                    'testing_location': {'type': 'string',
                                        'enum': ['bathroom', 'ensuite', 'kitchen', 'laundry', 'other']},
                    'pressure_cold_line': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'pressure_hot_line': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'pressure_shower_breech': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'pressure_bath_breech': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'flood_test_shower': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'flood_test_bath': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'spray_test_wall_tiles': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'spray_test_shower_screen': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'tile_condition': {'type': 'string',
                                      'enum': ['excellent', 'good', 'average', 'poor', 'very_poor']},
                    'grout_condition': {'type': 'string',
                                       'enum': ['excellent', 'good', 'average', 'poor', 'very_poor']},
                    'silicone_condition': {'type': 'string',
                                          'enum': ['excellent', 'good', 'average', 'poor', 'very_poor']},
                    'silicone_around_spindles': {'type': 'boolean'},
                    'conclusion': {'type': 'string'},
                    'front_of_dwelling': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                         'description': 'Repeat field for multiple files'},
                    'damage_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                     'description': 'Repeat field for multiple files'},
                    'whole_area_photo': {'type': 'string', 'format': 'binary',
                                        'description': 'Single image'},
                    'test_results_photo': {'type': 'string', 'format': 'binary',
                                          'description': 'Single image'},
                    'spindle_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                      'description': 'Repeat field for multiple files'},
                    'job_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                  'description': 'Repeat field for multiple files'},
                }
            }
        },
        responses={
            201: OpenApiResponse(description="Leak Inspection Report submitted successfully"),
            400: OpenApiResponse(description="Validation error or already submitted"),
            403: OpenApiResponse(description="Admin/manager cannot submit"),
        }
    )
    def post(self, request, job_report_id):
        return _handle_submit(request, job_report_id, ReportType.LEAK_INSPECTION)


class SprayTestSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['reports'],
        summary="Submit Spray Test Report",
        description="Submit a Spray Test Report. Employee only. multipart/form-data.",
        request={
            'multipart/form-data': {
                'type': 'object',
                'required': ['attendance_datetime'],
                'properties': {
                    'attendance_datetime': {'type': 'string', 'format': 'date-time',
                                           'description': 'REQUIRED. ISO 8601 e.g. 2026-03-12T09:30:00'},
                    'property_construction': {'type': 'string',
                                             'enum': ['brick_veneer', 'double_brick']},
                    'discussion_with_insured': {'type': 'string'},
                    'resultant_damage': {'type': 'string'},
                    'testing_location': {'type': 'string',
                                        'enum': [
                                            'bathroom', 'ensuite', 'kitchen', 'laundry',
                                            'external_wall', 'balcony', 'window', 'door',
                                            'roller_door', 'other'
                                        ]},
                    'flood_test': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'flood_test_notes': {'type': 'string'},
                    'spray_test': {'type': 'string', 'enum': ['passed', 'failed', 'na']},
                    'spray_test_notes': {'type': 'string'},
                    'tile_condition': {'type': 'string',
                                      'enum': ['excellent', 'good', 'average', 'poor', 'very_poor']},
                    'tile_condition_notes': {'type': 'string'},
                    'grout_condition': {'type': 'string',
                                       'enum': ['excellent', 'good', 'average', 'poor', 'very_poor']},
                    'grout_condition_notes': {'type': 'string'},
                    'silicone_condition': {'type': 'string',
                                          'enum': ['excellent', 'good', 'average', 'poor', 'very_poor']},
                    'silicone_condition_notes': {'type': 'string'},
                    'conclusion': {'type': 'string'},
                    'front_of_dwelling': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                         'description': 'Repeat field for multiple files'},
                    'damage_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                     'description': 'Repeat field for multiple files'},
                    'whole_area_photo': {'type': 'string', 'format': 'binary',
                                        'description': 'Single image'},
                    'job_photos': {'type': 'array', 'items': {'type': 'string', 'format': 'binary'},
                                  'description': 'Repeat field for multiple files'},
                }
            }
        },
        responses={
            201: OpenApiResponse(description="Spray Test Report submitted successfully"),
            400: OpenApiResponse(description="Validation error or already submitted"),
            403: OpenApiResponse(description="Admin/manager cannot submit"),
        }
    )
    def post(self, request, job_report_id):
        return _handle_submit(request, job_report_id, ReportType.SPRAY_TEST)


# ==================== SUBMISSION VIEW — read submitted data (UNCHANGED) ====================

class ReportSubmissionView(APIView):
    """
    GET /api/reports/{job_report_id}/submission/
    Unchanged — reads submitted report regardless of which typed endpoint was used.
    Uses REPORT_REGISTRY to route to the correct read serializer.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['reports'],
        summary="View submitted report",
        description="View full submitted data. Employee (who submitted) + admin/manager."
    )
    def get(self, request, job_report_id):
        user = request.user

        if user.is_superuser or user.is_staff:
            job_report = get_object_or_404(
                JobReport.objects.select_related('job', 'job__client', 'job__assigned_to'),
                id=job_report_id
            )
        else:
            job_report = _get_job_report_for_employee(job_report_id, user)

        if not job_report.is_submitted:
            return Response(
                {'error': 'This report has not been submitted yet.'},
                status=status.HTTP_404_NOT_FOUND
            )

        entry = REPORT_REGISTRY.get(job_report.report_type, (None, None, None, None))
        read_serializer_class = entry[2]
        related_name = entry[3]

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


# ==================== PDF DOWNLOAD (UNCHANGED) ====================

class ReportDownloadView(APIView):
    """
    GET /api/reports/{job_report_id}/download/
    Unchanged — routes to correct PDF builder via REPORT_REGISTRY.
    """
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['reports'],
        summary="Download report PDF",
        description="Generate and download submitted report as PDF. Admin/manager only."
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

        try:
            from .pdf.generator import generate_pdf
            pdf_buffer = generate_pdf(job_report, submission)
        except Exception as e:
            return Response(
                {'error': f'PDF generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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