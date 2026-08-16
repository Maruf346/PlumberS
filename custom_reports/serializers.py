import base64
import uuid as uuid_lib

from django.core.files.base import ContentFile
from rest_framework import serializers

from .models import *


class CustomReportFieldSerializer(serializers.ModelSerializer):
    options_list = serializers.ReadOnlyField()

    class Meta:
        model = CustomReportField
        fields = [
            'id', 'label', 'field_type',
            'options', 'options_list',
            'is_required', 'order', 'helper_text',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'options_list', 'created_at', 'updated_at']

    def validate(self, data):
        field_type = data.get('field_type', getattr(self.instance, 'field_type', None))
        options = data.get('options', getattr(self.instance, 'options', ''))
        select_types = [FieldType.SELECT, FieldType.MULTI_SELECT]

        if field_type in select_types and not options:
            raise serializers.ValidationError({
                'options': f'Options are required for field type "{field_type}".'
            })
        if field_type not in select_types and options:
            data['options'] = ''

        return data


class CustomReportFieldWriteSerializer(CustomReportFieldSerializer):
    def validate_order(self, value):
        template = self.context.get('template')
        qs = CustomReportField.objects.filter(template=template, order=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f'A field with order {value} already exists in this template. '
                'Use the reorder endpoint to rearrange fields.'
            )
        return value


class CustomReportTemplateListSerializer(serializers.ModelSerializer):
    field_count = serializers.SerializerMethodField()

    class Meta:
        model = CustomReportTemplate
        fields = [
            'id', 'name', 'description',
            'is_active', 'field_count',
            'created_at', 'updated_at',
        ]

    def get_field_count(self, obj):
        return obj.fields.count()


class CustomReportTemplateDetailSerializer(serializers.ModelSerializer):
    fields = CustomReportFieldSerializer(many=True, read_only=True)

    class Meta:
        model = CustomReportTemplate
        fields = [
            'id', 'name', 'description',
            'is_active', 'fields',
            'created_at', 'updated_at',
        ]


class CustomReportTemplateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomReportTemplate
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        value = value.strip()
        qs = CustomReportTemplate.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A custom report template with this name already exists.')
        return value


class FieldReorderSerializer(serializers.Serializer):
    class FieldOrderItem(serializers.Serializer):
        id = serializers.UUIDField()
        order = serializers.IntegerField(min_value=0)

    fields = FieldOrderItem(many=True)

    def validate_fields(self, value):
        if not value:
            raise serializers.ValidationError('Provide at least one field to reorder.')
        orders = [item['order'] for item in value]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError('Duplicate order values are not allowed.')
        return value


def decode_base64_file(base64_string, filename_prefix='file'):
    try:
        if ';base64,' in base64_string:
            header, data = base64_string.split(';base64,')
            mime = header.split(':')[-1]
            ext_map = {
                'image/jpeg': 'jpg',
                'image/png': 'png',
                'image/webp': 'webp',
                'application/pdf': 'pdf',
                'image/heic': 'heic',
            }
            extension = ext_map.get(mime, 'bin')
        else:
            data = base64_string
            extension = 'bin'

        decoded = base64.b64decode(data)
        filename = f"{filename_prefix}_{uuid_lib.uuid4().hex[:8]}.{extension}"
        return ContentFile(decoded, name=filename)
    except Exception:
        raise serializers.ValidationError('Invalid base64 file data.')


class CustomReportResponseInputSerializer(serializers.Serializer):
    field_id = serializers.UUIDField()
    value = serializers.CharField(allow_blank=True, required=False, default='')

    def validate(self, data):
        try:
            field = CustomReportField.objects.get(id=data['field_id'])
        except CustomReportField.DoesNotExist:
            raise serializers.ValidationError(
                {'field_id': f"Field {data['field_id']} not found."}
            )

        value = data.get('value', '')
        field_type = field.field_type

        if field.is_required and not value.strip():
            raise serializers.ValidationError({'value': f"'{field.label}' is required."})

        if field_type == FieldType.CHECKBOX and value.lower() not in ['true', 'false', '']:
            raise serializers.ValidationError({'value': f"'{field.label}' must be 'true' or 'false'."})

        if field_type == FieldType.NUMBER and value.strip():
            try:
                float(value)
            except ValueError:
                raise serializers.ValidationError({'value': f"'{field.label}' must be a valid number."})

        if field_type == FieldType.SELECT and value.strip():
            allowed = field.options_list
            if value not in allowed:
                raise serializers.ValidationError({
                    'value': f"'{value}' is not a valid option for '{field.label}'. Allowed: {allowed}"
                })

        if field_type == FieldType.MULTI_SELECT and value.strip():
            allowed = field.options_list
            selected = [v.strip() for v in value.split(',')]
            invalid = [v for v in selected if v not in allowed]
            if invalid:
                raise serializers.ValidationError({
                    'value': f"Invalid options {invalid} for '{field.label}'. Allowed: {allowed}"
                })

        data['_field'] = field
        return data


class CustomReportSubmitSerializer(serializers.Serializer):
    responses = CustomReportResponseInputSerializer(many=True)

    def validate_responses(self, value):
        if not value:
            raise serializers.ValidationError('At least one response must be provided.')
        field_ids = [str(r['field_id']) for r in value]
        if len(field_ids) != len(set(field_ids)):
            raise serializers.ValidationError('Duplicate field_id entries found.')
        return value


class CustomReportResponseReadSerializer(serializers.ModelSerializer):
    field_label = serializers.CharField(source='field.label', read_only=True)
    field_type = serializers.CharField(source='field.field_type', read_only=True)
    field_order = serializers.IntegerField(source='field.order', read_only=True)

    class Meta:
        model = CustomReportResponse
        fields = [
            'id', 'field', 'field_label',
            'field_type', 'field_order',
            'value', 'file',
        ]
        read_only_fields = fields


class CustomReportSubmissionDetailSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    responses = CustomReportResponseReadSerializer(many=True, read_only=True)
    job_id = serializers.CharField(source='job.job_id', read_only=True)
    job_name = serializers.CharField(source='job.job_name', read_only=True)

    class Meta:
        model = CustomReportSubmission
        fields = [
            'id', 'job', 'job_id', 'job_name',
            'template', 'template_name',
            'employee', 'employee_name', 'employee_email',
            'responses', 'submitted_at',
        ]
        read_only_fields = fields


class CustomReportSubmissionListSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    job_id = serializers.CharField(source='job.job_id', read_only=True)
    job_name = serializers.CharField(source='job.job_name', read_only=True)
    response_count = serializers.SerializerMethodField()

    class Meta:
        model = CustomReportSubmission
        fields = [
            'id', 'job', 'job_id', 'job_name',
            'template', 'template_name',
            'employee', 'employee_name',
            'response_count', 'submitted_at',
        ]

    def get_response_count(self, obj):
        return obj.responses.count()


class JobCustomReportsStatusSerializer(serializers.Serializer):
    class ReportStatusItem(serializers.Serializer):
        template_id = serializers.UUIDField()
        template_name = serializers.CharField()
        is_submitted = serializers.BooleanField()
        submitted_at = serializers.DateTimeField(allow_null=True)
        submission_id = serializers.UUIDField(allow_null=True)

    job_id = serializers.CharField()
    job_name = serializers.CharField()
    client_address = serializers.CharField(allow_null=True)
    reports = ReportStatusItem(many=True)
