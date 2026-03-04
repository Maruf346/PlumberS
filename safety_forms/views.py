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