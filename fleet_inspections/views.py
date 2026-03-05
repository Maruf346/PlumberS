from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter
import json

from .models import *
from .serializers import *
from user.permissions import IsAdminOrManager, IsAdminOrManagerOrEmployee


def _check_vehicle_permission(vehicle, user):
    """
    Employees must have an active job (PENDING or IN_PROGRESS)
    with this vehicle. Admins and managers bypass this check.
    Returns (allowed: bool, error_response or None)
    """
    if user.is_superuser or user.is_staff:
        return True, None

    from jobs.models import Job, JobStatus
    has_active_job = Job.objects.filter(
        assigned_to=user,
        vehicle=vehicle,
        status__in=[JobStatus.PENDING, JobStatus.IN_PROGRESS]
    ).exists()

    if not has_active_job:
        return False, Response(
            {
                'error': 'You are not authorized to inspect this vehicle. '
                         'You must have an active job assigned with this vehicle.'
            },
            status=status.HTTP_403_FORBIDDEN
        )
    return True, None


class SubmitInspectionView(APIView):
    """
    Single endpoint — employee submits the full inspection at once.

    Multipart form data structure:
        notes: "optional overall notes"
        items: JSON string of checklist items —
               [
                 {"category": "lights", "is_ok": true},
                 {"category": "tires", "is_ok": false, "issue_detail": "worn out"},
                 ...
               ]
        photos_tires_0: <image file>
        photos_tires_1: <image file>
        photos_lights_0: <image file>

    Photo key convention: photos_<category>_<index>
    e.g. photos_tires_0, photos_tires_1, photos_body_exterior_0
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Submit vehicle inspection",
        description=(
            "Submit a full vehicle inspection in one multipart call. "
            "Send 'items' as a JSON string and photos keyed as "
            "'photos_<category>_<index>' e.g. 'photos_tires_0'."
        ),
    )
    def post(self, request, vehicle_id):
        from fleets.models import Vehicle
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, is_active=True)

        # Permission check
        allowed, error = _check_vehicle_permission(vehicle, request.user)
        if not allowed:
            return error

        # Parse items — frontend sends as JSON string in multipart
        raw_items = request.data.get('items')
        if not raw_items:
            return Response(
                {'error': 'items field is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            items_data = json.loads(raw_items)
        except (json.JSONDecodeError, TypeError):
            return Response(
                {'error': 'items must be a valid JSON string.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payload = {
            'notes': request.data.get('notes', ''),
            'items': items_data
        }

        serializer = InspectionSubmitSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        # Create inspection record
        inspection = VehicleInspection.objects.create(
            vehicle=vehicle,
            inspected_by=request.user,
            notes=validated.get('notes', ''),
            has_open_issue=False  # computed below
        )

        has_issue = False

        for item_data in validated['items']:
            category = item_data['category']
            is_ok = item_data['is_ok']
            issue_detail = item_data.get('issue_detail', '')

            if not is_ok:
                has_issue = True

            check_item = InspectionCheckItem.objects.create(
                inspection=inspection,
                category=category,
                is_ok=is_ok,
                issue_detail=issue_detail
            )

            # Collect photos for this category
            # Key convention: photos_<category>_<index>
            index = 0
            while True:
                photo_key = f'photos_{category}_{index}'
                photo_file = request.FILES.get(photo_key)
                if not photo_file:
                    break
                InspectionCheckPhoto.objects.create(
                    check_item=check_item,
                    photo=photo_file,
                    caption=request.data.get(f'captions_{category}_{index}', '')
                )
                index += 1

        # Save computed has_open_issue
        inspection.has_open_issue = has_issue
        inspection.save()

        # Auto-update vehicle status
        vehicle.update_status()

        return Response(
            {
                'message': 'Inspection submitted successfully.',
                'has_open_issue': has_issue,
                'data': VehicleInspectionDetailSerializer(inspection).data
            },
            status=status.HTTP_201_CREATED
        )


# ==================== HISTORY VIEWS ====================

class VehicleInspectionHistoryView(ListAPIView):
    """All authenticated staff — inspection history for a specific vehicle."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = VehicleInspectionListSerializer

    def get_queryset(self):
        return VehicleInspection.objects.filter(
            vehicle__id=self.kwargs['vehicle_id']
        ).select_related('vehicle', 'inspected_by').order_by('-inspected_at')

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Vehicle inspection history"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class InspectionDetailView(RetrieveAPIView):
    """Full detail of a single inspection — all authenticated staff."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = VehicleInspectionDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return VehicleInspection.objects.select_related(
            'vehicle', 'inspected_by'
        ).prefetch_related('check_items__photos')

    @extend_schema(tags=['fleet-inspections'], summary="Inspection detail")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AllInspectionsListView(ListAPIView):
    """Admin/manager — all inspections across all vehicles with filters."""
    permission_classes = [IsAdminOrManager]
    serializer_class = VehicleInspectionListSerializer

    def get_queryset(self):
        qs = VehicleInspection.objects.select_related(
            'vehicle', 'inspected_by'
        ).order_by('-inspected_at')

        vehicle = self.request.query_params.get('vehicle')
        if vehicle:
            qs = qs.filter(vehicle__id=vehicle)

        inspector = self.request.query_params.get('inspector')
        if inspector:
            qs = qs.filter(inspected_by__id=inspector)

        has_issue = self.request.query_params.get('has_issue')
        if has_issue == 'true':
            qs = qs.filter(has_open_issue=True)
        elif has_issue == 'false':
            qs = qs.filter(has_open_issue=False)

        return qs

    @extend_schema(
        tags=['fleet-inspections'],
        summary="All inspections (admin/manager)",
        parameters=[
            OpenApiParameter('vehicle', str, description='Filter by vehicle UUID'),
            OpenApiParameter('inspector', str, description='Filter by employee UUID'),
            OpenApiParameter('has_issue', str, description='true | false'),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)