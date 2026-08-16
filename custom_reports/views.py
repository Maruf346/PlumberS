from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from user.permissions import IsAdmin, IsAdminOrManager, IsAdminOrManagerOrEmployee
from .models import *
from .serializers import *


class CustomReportTemplateListView(ListAPIView):
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = CustomReportTemplateListSerializer

    def get_queryset(self):
        if self.request.user.is_superuser and self.request.query_params.get('all') == 'true':
            return CustomReportTemplate.objects.all()
        return CustomReportTemplate.objects.filter(is_active=True)

    @extend_schema(
        tags=['custom-reports'],
        summary="List custom report templates",
        description="Returns active custom report templates. Admin can pass ?all=true to include inactive templates."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class CustomReportTemplateDetailView(RetrieveAPIView):
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = CustomReportTemplateDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        if self.request.user.is_superuser:
            return CustomReportTemplate.objects.all()
        return CustomReportTemplate.objects.filter(is_active=True)

    @extend_schema(tags=['custom-reports'], summary="Retrieve custom report template with fields")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminCustomReportTemplateCreateView(APIView):
    permission_classes = [IsAdmin]
    serializer_class = CustomReportTemplateWriteSerializer

    @extend_schema(
        tags=['custom-reports'],
        summary="Create custom report template",
        request=CustomReportTemplateWriteSerializer,
        responses={201: CustomReportTemplateDetailSerializer}
    )
    def post(self, request):
        serializer = CustomReportTemplateWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response(
            {
                'message': 'Custom report template created.',
                'data': CustomReportTemplateDetailSerializer(template).data,
            },
            status=status.HTTP_201_CREATED
        )


class AdminCustomReportTemplateUpdateView(APIView):
    permission_classes = [IsAdmin]

    def get_object(self, id):
        return get_object_or_404(CustomReportTemplate, id=id)

    @extend_schema(
        tags=['custom-reports'],
        summary="Update custom report template",
        request=CustomReportTemplateWriteSerializer,
        responses={200: CustomReportTemplateDetailSerializer}
    )
    def patch(self, request, id):
        template = self.get_object(id)
        serializer = CustomReportTemplateWriteSerializer(
            template, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response(
            {
                'message': 'Custom report template updated.',
                'data': CustomReportTemplateDetailSerializer(template).data,
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(tags=['custom-reports'], summary="Delete custom report template", responses={204: None})
    def delete(self, request, id):
        template = self.get_object(id)
        template.delete()
        return Response(
            {'message': 'Custom report template deleted.'},
            status=status.HTTP_204_NO_CONTENT
        )


class AdminCustomReportFieldCreateView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['custom-reports'],
        summary="Add field to custom report template",
        request=CustomReportFieldWriteSerializer,
        responses={201: CustomReportFieldSerializer}
    )
    def post(self, request, template_id):
        template = get_object_or_404(CustomReportTemplate, id=template_id)
        serializer = CustomReportFieldWriteSerializer(
            data=request.data,
            context={'template': template, 'request': request}
        )
        serializer.is_valid(raise_exception=True)
        field = serializer.save(template=template)
        return Response(
            {
                'message': 'Field added.',
                'data': CustomReportFieldSerializer(field).data,
            },
            status=status.HTTP_201_CREATED
        )


class AdminCustomReportFieldUpdateView(APIView):
    permission_classes = [IsAdmin]

    def get_object(self, template_id, field_id):
        return get_object_or_404(CustomReportField, id=field_id, template__id=template_id)

    @extend_schema(
        tags=['custom-reports'],
        summary="Update custom report field",
        request=CustomReportFieldWriteSerializer,
        responses={200: CustomReportFieldSerializer}
    )
    def patch(self, request, template_id, field_id):
        field = self.get_object(template_id, field_id)
        serializer = CustomReportFieldWriteSerializer(
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
                'data': CustomReportFieldSerializer(field).data,
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(tags=['custom-reports'], summary="Delete custom report field", responses={204: None})
    def delete(self, request, template_id, field_id):
        field = self.get_object(template_id, field_id)
        field.delete()
        return Response({'message': 'Field deleted.'}, status=status.HTTP_204_NO_CONTENT)


class AdminCustomReportFieldReorderView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['custom-reports'],
        summary="Reorder custom report fields",
        request=FieldReorderSerializer,
        responses={200: CustomReportTemplateDetailSerializer}
    )
    def post(self, request, template_id):
        template = get_object_or_404(CustomReportTemplate, id=template_id)
        serializer = FieldReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        incoming = serializer.validated_data['fields']
        incoming_ids = [str(item['id']) for item in incoming]
        template_field_ids = set(
            str(fid) for fid in template.fields.values_list('id', flat=True)
        )
        for fid in incoming_ids:
            if fid not in template_field_ids:
                return Response(
                    {'error': f'Field {fid} does not belong to this template.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        for item in incoming:
            CustomReportField.objects.filter(
                id=item['id'], template=template
            ).update(order=item['order'])

        template.refresh_from_db()
        return Response(
            {
                'message': 'Fields reordered.',
                'data': CustomReportTemplateDetailSerializer(template).data,
            },
            status=status.HTTP_200_OK
        )


class CustomReportFieldTypeListView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(tags=['custom-reports'], summary="List custom report field types")
    def get(self, request):
        types = [
            {'value': choice[0], 'label': choice[1]}
            for choice in FieldType.choices
        ]
        return Response(types, status=status.HTTP_200_OK)


class JobCustomReportsView(APIView):
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['custom-reports'],
        summary="Job custom reports status",
        description="List all custom reports attached to a job with submission status per report."
    )
    def get(self, request, job_id):
        from jobs.models import Job

        if request.user.is_superuser or request.user.is_staff:
            job = get_object_or_404(Job, id=job_id)
        else:
            job = get_object_or_404(Job, id=job_id, assigned_to=request.user)

        attached_reports = job.custom_reports.filter(is_active=True)
        reports_status = []
        for template in attached_reports:
            submission = CustomReportSubmission.objects.filter(
                job=job,
                template=template,
                employee=request.user
            ).first()
            reports_status.append({
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
            'reports': reports_status,
        }, status=status.HTTP_200_OK)


class CustomReportTemplateDetailForEmployeeView(APIView):
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(tags=['custom-reports'], summary="Custom report template fields for a job")
    def get(self, request, job_id, template_id):
        from jobs.models import Job

        if request.user.is_superuser or request.user.is_staff:
            job = get_object_or_404(Job, id=job_id)
        else:
            job = get_object_or_404(Job, id=job_id, assigned_to=request.user)

        template = get_object_or_404(
            CustomReportTemplate,
            id=template_id,
            is_active=True,
            jobs=job
        )
        already_submitted = CustomReportSubmission.objects.filter(
            job=job,
            template=template,
            employee=request.user
        ).exists()

        return Response({
            'job_id': job.job_id,
            'job_name': job.job_name,
            'client_address': job.client.address if job.client else None,
            'already_submitted': already_submitted,
            'template': CustomReportTemplateDetailSerializer(template).data,
        }, status=status.HTTP_200_OK)


class CustomReportSubmitView(APIView):
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [JSONParser]

    @extend_schema(
        tags=['custom-reports'],
        summary="Submit custom report",
        request=CustomReportSubmitSerializer,
        responses={201: CustomReportSubmissionDetailSerializer}
    )
    def post(self, request, job_id, template_id):
        from jobs.models import ActivityType, Job, JobActivity

        if request.user.is_superuser or request.user.is_staff:
            job = get_object_or_404(Job, id=job_id)
        else:
            job = get_object_or_404(Job, id=job_id, assigned_to=request.user)

        template = get_object_or_404(
            CustomReportTemplate,
            id=template_id,
            is_active=True,
            jobs=job
        )

        if CustomReportSubmission.objects.filter(
            job=job,
            template=template,
            employee=request.user
        ).exists():
            return Response(
                {'error': 'You have already submitted this custom report for this job.'},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        serializer = CustomReportSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_responses = serializer.validated_data['responses']

        for response_data in validated_responses:
            field = response_data['_field']
            if field.template_id != template.id:
                return Response(
                    {'error': f'Field {field.id} does not belong to this custom report template.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        submission = CustomReportSubmission.objects.create(
            job=job,
            template=template,
            employee=request.user
        )

        for response_data in validated_responses:
            field = response_data['_field']
            value = response_data.get('value', '')

            if field.field_type == FieldType.FILE and value.strip():
                try:
                    file_content = decode_base64_file(
                        value,
                        filename_prefix=f"cr_{field.label.lower().replace(' ', '_')}"
                    )
                    CustomReportResponse.objects.create(
                        submission=submission,
                        field=field,
                        value='',
                        file=file_content
                    )
                except Exception:
                    CustomReportResponse.objects.create(
                        submission=submission,
                        field=field,
                        value=value
                    )
            else:
                CustomReportResponse.objects.create(
                    submission=submission,
                    field=field,
                    value=value
                )

        JobActivity.objects.create(
            job=job,
            activity_type=ActivityType.REPORT_SUBMITTED,
            actor=request.user,
            description=f"Custom report '{template.name}' submitted"
        )

        return Response(
            {
                'message': f"'{template.name}' submitted successfully.",
                'data': CustomReportSubmissionDetailSerializer(submission).data,
            },
            status=status.HTTP_201_CREATED
        )


class CustomReportSubmissionDetailView(RetrieveAPIView):
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = CustomReportSubmissionDetailSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return CustomReportSubmission.objects.all()
        return CustomReportSubmission.objects.filter(employee=user)

    def get_object(self):
        return get_object_or_404(
            self.get_queryset().prefetch_related('responses__field'),
            id=self.kwargs['submission_id']
        )

    @extend_schema(tags=['custom-reports'], summary="View custom report submission detail")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminJobCustomReportSubmissionsView(ListAPIView):
    permission_classes = [IsAdminOrManager]
    serializer_class = CustomReportSubmissionListSerializer

    def get_queryset(self):
        return CustomReportSubmission.objects.filter(
            job__id=self.kwargs['job_id']
        ).select_related(
            'template', 'employee', 'job'
        ).order_by('-submitted_at')

    @extend_schema(tags=['custom-reports'], summary="All custom report submissions for a job")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
