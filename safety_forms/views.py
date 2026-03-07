from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema

from .models import *
from .serializers import *
from user.permissions import *
from rest_framework.parsers import JSONParser
from user.permissions import IsAdminOrManager, IsAdminOrManagerOrEmployee


# ==================== TEMPLATE VIEWS ====================

class SafetyFormTemplateListView(ListAPIView):
    """
    GET — all authenticated staff see active templates.
    Admin sees all (active + inactive) via query param ?all=true.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = SafetyFormTemplateListSerializer

    def get_queryset(self):
        if self.request.user.is_superuser and self.request.query_params.get('all') == 'true':
            return SafetyFormTemplate.objects.all()
        return SafetyFormTemplate.objects.filter(is_active=True)

    @extend_schema(
        tags=['safety-forms'],
        summary="List form templates",
        description=(
            "Returns active form templates for all staff. "
            "Admin can pass ?all=true to include inactive templates."
        )
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SafetyFormTemplateDetailView(RetrieveAPIView):
    """
    Any authenticated staff retrieves a template with all its fields nested.
    Admin can view inactive templates; others only see active ones.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = SafetyFormTemplateDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        if self.request.user.is_superuser:
            return SafetyFormTemplate.objects.all()
        return SafetyFormTemplate.objects.filter(is_active=True)

    @extend_schema(
        tags=['safety-forms'],
        summary="Retrieve form template with fields",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminSafetyFormTemplateCreateView(APIView):
    """Admin creates a new form template (no fields yet)."""
    permission_classes = [IsAdmin]
    serializer_class = SafetyFormTemplateWriteSerializer

    @extend_schema(
        tags=['safety-forms'],
        summary="Create form template",
        description="Admin only. Create a named form template. Add fields separately.",
        request=SafetyFormTemplateWriteSerializer,
        responses={201: SafetyFormTemplateDetailSerializer}
    )
    def post(self, request):
        serializer = SafetyFormTemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response(
            {
                'message': 'Form template created.',
                'data': SafetyFormTemplateDetailSerializer(template).data
            },
            status=status.HTTP_201_CREATED
        )


class AdminSafetyFormTemplateUpdateView(APIView):
    # Admin updates or deletes a form template.
    permission_classes = [IsAdmin]

    def get_object(self, id):
        return get_object_or_404(SafetyFormTemplate, id=id)

    @extend_schema(
        tags=['safety-forms'],
        summary="Update form template",
        request=SafetyFormTemplateWriteSerializer,
        responses={200: SafetyFormTemplateDetailSerializer}
    )
    def patch(self, request, id):
        template = self.get_object(id)
        serializer = SafetyFormTemplateWriteSerializer(
            template, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response(
            {
                'message': 'Form template updated.',
                'data': SafetyFormTemplateDetailSerializer(template).data
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(
        tags=['safety-forms'],
        summary="Delete form template",
        description=(
            "Permanently deletes the template and all its fields. "
            "Consider setting is_active=False instead to preserve history."
        ),
        responses={204: None}
    )
    def delete(self, request, id):
        template = self.get_object(id)
        template.delete()
        return Response(
            {'message': 'Form template deleted.'},
            status=status.HTTP_204_NO_CONTENT
        )


# ==================== FIELD VIEWS ====================

class AdminFieldCreateView(APIView):
    # Admin adds a new field to an existing template.
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['safety-forms'],
        summary="Add field to template",
        request=SafetyFormFieldWriteSerializer,
        responses={201: SafetyFormFieldSerializer}
    )
    def post(self, request, template_id):
        template = get_object_or_404(SafetyFormTemplate, id=template_id)
        serializer = SafetyFormFieldWriteSerializer(
            data=request.data,
            context={'template': template, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        field = serializer.save(template=template)
        return Response(
            {
                'message': 'Field added.',
                'data': SafetyFormFieldSerializer(field).data
            },
            status=status.HTTP_201_CREATED
        )


class AdminFieldUpdateView(APIView):
    # Admin updates or deletes a single field.
    permission_classes = [IsAdmin]

    def get_object(self, template_id, field_id):
        return get_object_or_404(
            SafetyFormField,
            id=field_id,
            template__id=template_id
        )

    @extend_schema(
        tags=['safety-forms'],
        summary="Update field",
        request=SafetyFormFieldWriteSerializer,
        responses={200: SafetyFormFieldSerializer}
    )
    def patch(self, request, template_id, field_id):
        field = self.get_object(template_id, field_id)
        serializer = SafetyFormFieldWriteSerializer(
            field,
            data=request.data,
            partial=True,
            context={'template': field.template, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        field = serializer.save()
        return Response(
            {
                'message': 'Field updated.',
                'data': SafetyFormFieldSerializer(field).data
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(
        tags=['safety-forms'],
        summary="Delete field",
        responses={204: None}
    )
    def delete(self, request, template_id, field_id):
        field = self.get_object(template_id, field_id)
        field.delete()
        return Response(
            {'message': 'Field deleted.'},
            status=status.HTTP_204_NO_CONTENT
        )


class AdminFieldReorderView(APIView):
    """
    Bulk reorder fields in a template via drag-and-drop.
    Accepts: {"fields": [{"id": "uuid", "order": 1}, ...]}
    """
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['safety-forms'],
        summary="Reorder fields",
        description="Submit full new ordering for all fields in a template.",
        request=FieldReorderSerializer,
        responses={200: SafetyFormTemplateDetailSerializer}
    )
    def post(self, request, template_id):
        template = get_object_or_404(SafetyFormTemplate, id=template_id)
        serializer = FieldReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        incoming = serializer.validated_data['fields']
        incoming_ids = [str(item['id']) for item in incoming]

        # Validate all IDs belong to this template
        template_field_ids = set(
            str(fid) for fid in
            template.fields.values_list('id', flat=True)
        )
        for fid in incoming_ids:
            if fid not in template_field_ids:
                return Response(
                    {'error': f'Field {fid} does not belong to this template.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Apply new order values
        for item in incoming:
            SafetyFormField.objects.filter(
                id=item['id'], template=template
            ).update(order=item['order'])

        template.refresh_from_db()
        return Response(
            {
                'message': 'Fields reordered.',
                'data': SafetyFormTemplateDetailSerializer(template).data
            },
            status=status.HTTP_200_OK
        )


class FieldTypeListView(APIView):
    """
    Returns all available field types.
    Frontend uses this to populate the 'Type' dropdown when building forms.
    """
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['safety-forms'],
        summary="List available field types",
    )
    def get(self, request):
        types = [
            {'value': choice[0], 'label': choice[1]}
            for choice in FieldType.choices
        ]
        return Response(types, status=status.HTTP_200_OK)
    
    
class JobSafetyFormsView(APIView):
    """
    GET — Employee views all safety forms attached to a specific job
    with submission status for each.
    Shows: job_id, job_name, client address, and per-form status.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['safety-forms'],
        summary="Job safety forms status",
        description="List all safety forms attached to a job with submission status per form."
    )
    def get(self, request, job_id):
        from jobs.models import Job

        # Employee can only see their own job's forms
        if request.user.is_superuser or request.user.is_staff:
            job = get_object_or_404(Job, id=job_id)
        else:
            job = get_object_or_404(Job, id=job_id, assigned_to=request.user)

        attached_forms = job.safety_forms.filter(is_active=True)

        forms_status = []
        for template in attached_forms:
            submission = SafetyFormSubmission.objects.filter(
                job=job,
                template=template,
                employee=request.user
            ).first()

            forms_status.append({
                'template_id': template.id,
                'template_name': template.name,
                'is_submitted': submission is not None,
                'submitted_at': submission.submitted_at if submission else None,
                'submission_id': submission.id if submission else None,
            })

        return Response({
            'job_id': job.job_id,
            'job_name': job.job_name,
            'client_address': job.client.address if job.client else None,
            'forms': forms_status,
        }, status=status.HTTP_200_OK)


class SafetyFormTemplateDetailForEmployeeView(RetrieveAPIView):
    """
    GET — Employee views the full field structure of a specific
    safety form template before filling it in.
    Shows: job context + all form fields with their types and options.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['safety-forms'],
        summary="Safety form template fields (employee view)",
    )
    def get(self, request, job_id, template_id):
        from jobs.models import Job
        from .serializers import SafetyFormTemplateDetailSerializer

        if request.user.is_superuser or request.user.is_staff:
            job = get_object_or_404(Job, id=job_id)
        else:
            job = get_object_or_404(Job, id=job_id, assigned_to=request.user)

        # Confirm this template is actually attached to this job
        template = get_object_or_404(
            SafetyFormTemplate,
            id=template_id,
            is_active=True,
            jobs=job
        )

        # Check if already submitted
        already_submitted = SafetyFormSubmission.objects.filter(
            job=job,
            template=template,
            employee=request.user
        ).exists()

        return Response({
            'job_id': job.job_id,
            'job_name': job.job_name,
            'client_address': job.client.address if job.client else None,
            'already_submitted': already_submitted,
            'template': SafetyFormTemplateDetailSerializer(template).data,
        }, status=status.HTTP_200_OK)


class SafetyFormSubmitView(APIView):
    """
    POST — Employee submits a safety form for a specific job.
    One submission per form per job per employee — locked after submit.
    FILE fields accept base64 encoded strings.

    Payload:
    {
        "responses": [
            {"field_id": "<uuid>", "value": "Some text"},
            {"field_id": "<uuid>", "value": "true"},
            {"field_id": "<uuid>", "value": "Option A"},
            {"field_id": "<uuid>", "value": "data:image/jpeg;base64,..."}
        ]
    }
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=['safety-forms'],
        summary="Submit safety form",
        request=SafetyFormSubmitSerializer,
        responses={201: SafetyFormSubmissionDetailSerializer}
    )
    def post(self, request, job_id, template_id):
        from jobs.models import Job, JobActivity, ActivityType

        if request.user.is_superuser or request.user.is_staff:
            job = get_object_or_404(Job, id=job_id)
        else:
            job = get_object_or_404(Job, id=job_id, assigned_to=request.user)

        template = get_object_or_404(
            SafetyFormTemplate,
            id=template_id,
            is_active=True,
            jobs=job
        )

        # Lock check — one submission only
        if SafetyFormSubmission.objects.filter(
            job=job,
            template=template,
            employee=request.user
        ).exists():
            return Response(
                {'error': 'You have already submitted this form for this job.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate required fields coverage
        # Check all required fields have responses
        required_field_ids = set(
            str(fid) for fid in
            template.fields.filter(is_required=True).values_list('id', flat=True)
        )
        provided_field_ids = set(
            str(r.get('field_id', ''))
            for r in request.data.get('responses', [])
        )
        missing = required_field_ids - provided_field_ids
        if missing:
            return Response(
                {'error': f'Missing required fields: {list(missing)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SafetyFormSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_responses = serializer.validated_data['responses']

        # Create submission
        submission = SafetyFormSubmission.objects.create(
            job=job,
            template=template,
            employee=request.user
        )

        # Create responses
        for response_data in validated_responses:
            field = response_data['_field']
            value = response_data.get('value', '')

            if field.field_type == FieldType.FILE and value.strip():
                # Decode base64 file
                try:
                    file_content = decode_base64_file(
                        value,
                        filename_prefix=f"sf_{field.label.lower().replace(' ', '_')}"
                    )
                    SafetyFormResponse.objects.create(
                        submission=submission,
                        field=field,
                        value='',
                        file=file_content
                    )
                except Exception:
                    # File decode failed — save raw value as fallback
                    SafetyFormResponse.objects.create(
                        submission=submission,
                        field=field,
                        value=value
                    )
            else:
                SafetyFormResponse.objects.create(
                    submission=submission,
                    field=field,
                    value=value
                )

        # Log job activity
        JobActivity.objects.create(
            job=job,
            activity_type=ActivityType.SAFETY_FORM_SUBMITTED,
            actor=request.user,
            description=f"Safety form '{template.name}' submitted"
        )

        return Response(
            {
                'message': f"'{template.name}' submitted successfully.",
                'data': SafetyFormSubmissionDetailSerializer(submission).data
            },
            status=status.HTTP_201_CREATED
        )


class SafetyFormSubmissionDetailView(RetrieveAPIView):
    """
    GET — View a submitted form's responses.
    Accessible by the submitting employee and admin/manager.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = SafetyFormSubmissionDetailSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return SafetyFormSubmission.objects.all()
        # Employee can only see their own submissions
        return SafetyFormSubmission.objects.filter(employee=user)

    def get_object(self):
        return get_object_or_404(
            self.get_queryset().prefetch_related('responses__field'),
            id=self.kwargs['submission_id']
        )

    @extend_schema(
        tags=['safety-forms'],
        summary="View safety form submission detail"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminJobSafetySubmissionsView(ListAPIView):
    """
    GET — Admin/manager views all safety form submissions for a job.
    """
    permission_classes = [IsAdminOrManager]
    serializer_class = SafetyFormSubmissionListSerializer

    def get_queryset(self):
        return SafetyFormSubmission.objects.filter(
            job__id=self.kwargs['job_id']
        ).select_related(
            'template', 'employee', 'job'
        ).order_by('-submitted_at')

    @extend_schema(
        tags=['safety-forms'],
        summary="All safety form submissions for a job (admin/manager)"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)