from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import *
from .serializers import *
from user.permissions import IsAdmin, IsAdminOrManager, IsAdminOrManagerOrEmployee


def _get_vehicle_or_403(vehicle_id, employee):
    """
    Validates that the employee has an active job (PENDING or IN_PROGRESS)
    with the given vehicle. Returns the Vehicle instance or raises a
    clear error response dict.
    """
    from fleets.models import Vehicle
    from jobs.models import Job, JobStatus

    vehicle = get_object_or_404(Vehicle, id=vehicle_id, is_active=True)

    # Admin and managers bypass the job assignment check
    if employee.is_superuser or employee.is_staff:
        return vehicle, None

    has_active_job = Job.objects.filter(
        assigned_to=employee,
        vehicle=vehicle,
        status__in=[JobStatus.PENDING, JobStatus.IN_PROGRESS]
    ).exists()

    if not has_active_job:
        return None, Response(
            {
                'error': 'You are not authorized to inspect this vehicle. '
                         'You must have an active job assigned with this vehicle.'
            },
            status=status.HTTP_403_FORBIDDEN
        )

    return vehicle, None


# ==================== START / RESUME INSPECTION ====================

class StartOrResumeInspectionView(APIView):
    """
    POST — Employee starts a new inspection or resumes their existing draft.
    Only one DRAFT per employee per vehicle is allowed at a time.
    If a DRAFT already exists, it is returned instead of creating a new one.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Start or resume vehicle inspection",
        request=InspectionStartSerializer,
        responses={200: VehicleInspectionDetailSerializer}
    )
    def post(self, request):
        serializer = InspectionStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vehicle_id = serializer.validated_data['vehicle_id']
        vehicle, error = _get_vehicle_or_403(vehicle_id, request.user)
        if error:
            return error

        # Check for existing draft
        existing_draft = VehicleInspection.objects.filter(
            vehicle=vehicle,
            inspected_by=request.user,
            status=InspectionStatus.DRAFT
        ).first()

        if existing_draft:
            return Response(
                {
                    'message': 'Resuming existing draft inspection.',
                    'data': VehicleInspectionDetailSerializer(existing_draft).data
                },
                status=status.HTTP_200_OK
            )

        # Create new draft
        inspection = VehicleInspection.objects.create(
            vehicle=vehicle,
            inspected_by=request.user,
            status=InspectionStatus.DRAFT
        )
        return Response(
            {
                'message': 'Inspection started.',
                'data': VehicleInspectionDetailSerializer(inspection).data
            },
            status=status.HTTP_201_CREATED
        )


# ==================== CHECK ITEM SAVE / UPDATE ====================

class SaveCheckItemView(APIView):
    """
    POST — Employee saves or updates a single checklist item on a draft inspection.
    If the category already exists on this inspection, it is updated.
    If not, it is created.
    This is the endpoint hit when employee toggles Yes/No and saves a row.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Save or update a checklist item",
        request=InspectionCheckItemWriteSerializer,
        responses={200: InspectionCheckItemSerializer}
    )
    def post(self, request, inspection_id):
        inspection = get_object_or_404(
            VehicleInspection,
            id=inspection_id,
            status=InspectionStatus.DRAFT
        )

        # Only the inspector or admin/manager can modify
        if not (request.user.is_staff or request.user.is_superuser):
            if inspection.inspected_by != request.user:
                return Response(
                    {'error': 'You can only modify your own inspection.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Upsert — update if category exists, create if not
        existing = InspectionCheckItem.objects.filter(
            inspection=inspection,
            category=request.data.get('category')
        ).first()

        serializer = InspectionCheckItemWriteSerializer(
            existing,
            data=request.data,
            partial=bool(existing)
        )
        serializer.is_valid(raise_exception=True)

        if existing:
            item = serializer.save()
            msg = 'Check item updated.'
        else:
            item = serializer.save(inspection=inspection)
            msg = 'Check item saved.'

        return Response(
            {
                'message': msg,
                'data': InspectionCheckItemSerializer(item).data
            },
            status=status.HTTP_200_OK
        )


# ==================== PHOTO UPLOAD / DELETE ====================

class CheckItemPhotoUploadView(APIView):
    """
    Employee uploads one or more photos to a specific check item.
    Only allowed on DRAFT inspections.
    Only relevant when check item is_ok=False.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Upload photos to a check item",
    )
    def post(self, request, inspection_id, check_item_id):
        inspection = get_object_or_404(
            VehicleInspection,
            id=inspection_id,
            status=InspectionStatus.DRAFT
        )

        if not (request.user.is_staff or request.user.is_superuser):
            if inspection.inspected_by != request.user:
                return Response(
                    {'error': 'You can only modify your own inspection.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        check_item = get_object_or_404(
            InspectionCheckItem,
            id=check_item_id,
            inspection=inspection
        )

        photos = request.FILES.getlist('photos')
        if not photos:
            return Response(
                {'error': 'No photos provided.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created = []
        for photo in photos:
            caption = request.data.get('caption', '')
            obj = InspectionCheckPhoto.objects.create(
                check_item=check_item,
                photo=photo,
                caption=caption
            )
            created.append(InspectionCheckPhotoSerializer(obj).data)

        return Response(
            {'message': f'{len(created)} photo(s) uploaded.', 'data': created},
            status=status.HTTP_201_CREATED
        )


class CheckItemPhotoDeleteView(APIView):
    """Delete a specific photo from a check item. Draft only."""
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Delete a check item photo",
        responses={204: None}
    )
    def delete(self, request, inspection_id, check_item_id, photo_id):
        inspection = get_object_or_404(
            VehicleInspection,
            id=inspection_id,
            status=InspectionStatus.DRAFT
        )

        if not (request.user.is_staff or request.user.is_superuser):
            if inspection.inspected_by != request.user:
                return Response(
                    {'error': 'You can only modify your own inspection.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        photo = get_object_or_404(
            InspectionCheckPhoto,
            id=photo_id,
            check_item__id=check_item_id,
            check_item__inspection=inspection
        )
        photo.delete()
        return Response({'message': 'Photo deleted.'}, status=status.HTTP_204_NO_CONTENT)


# ==================== SUBMIT INSPECTION ====================

class SubmitInspectionView(APIView):
    """
    Employee submits the inspection — DRAFT → SUBMITTED.
    On submit:
    1. has_open_issue is computed from check items.
    2. submitted_at is set.
    3. Vehicle.update_status() is called to reflect new inspection state.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Submit inspection",
        request=InspectionSubmitSerializer,
        responses={200: VehicleInspectionDetailSerializer}
    )
    def post(self, request, inspection_id):
        inspection = get_object_or_404(
            VehicleInspection,
            id=inspection_id,
            status=InspectionStatus.DRAFT
        )

        if not (request.user.is_staff or request.user.is_superuser):
            if inspection.inspected_by != request.user:
                return Response(
                    {'error': 'You can only submit your own inspection.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        serializer = InspectionSubmitSerializer(
            data=request.data,
            context={'inspection': inspection}
        )
        serializer.is_valid(raise_exception=True)

        # Compute has_open_issue
        has_issue = inspection.check_items.filter(is_ok=False).exists()

        # Finalize inspection
        inspection.has_open_issue = has_issue
        inspection.status = InspectionStatus.SUBMITTED
        inspection.submitted_at = timezone.now()
        inspection.notes = serializer.validated_data.get('notes', inspection.notes)
        inspection.save()

        # Auto-update vehicle status
        inspection.vehicle.update_status()

        return Response(
            {
                'message': 'Inspection submitted successfully.',
                'has_open_issue': has_issue,
                'data': VehicleInspectionDetailSerializer(inspection).data
            },
            status=status.HTTP_200_OK
        )


# ==================== INSPECTION HISTORY ====================

class VehicleInspectionHistoryView(ListAPIView):
    """
    All authenticated staff can view inspection history for a specific vehicle.
    Ordered by most recent first.
    Only SUBMITTED inspections appear in history.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = VehicleInspectionListSerializer

    def get_queryset(self):
        vehicle_id = self.kwargs['vehicle_id']
        return VehicleInspection.objects.filter(
            vehicle__id=vehicle_id,
            status=InspectionStatus.SUBMITTED
        ).select_related('vehicle', 'inspected_by').order_by('-submitted_at')

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Vehicle inspection history",
        description="Lists all submitted inspections for a vehicle. Visible to all authenticated staff."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class InspectionHistoryDetailView(RetrieveAPIView):
    """
    Full detail of a submitted inspection.
    All authenticated staff can view.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = VehicleInspectionDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return VehicleInspection.objects.filter(
            status=InspectionStatus.SUBMITTED
        ).select_related('vehicle', 'inspected_by').prefetch_related(
            'check_items__photos'
        )

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Inspection history detail",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MyDraftInspectionView(RetrieveAPIView):
    """
    Employee retrieves their current DRAFT inspection for a vehicle.
    Used when resuming — mobile app calls this on entering the inspection screen.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = VehicleInspectionDetailSerializer

    @extend_schema(
        tags=['fleet-inspections'],
        summary="Get my current draft inspection for a vehicle",
    )
    def get(self, request, vehicle_id):
        inspection = VehicleInspection.objects.filter(
            vehicle__id=vehicle_id,
            inspected_by=request.user,
            status=InspectionStatus.DRAFT
        ).prefetch_related('check_items__photos').first()

        if not inspection:
            return Response(
                {'message': 'No active draft inspection for this vehicle.'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            VehicleInspectionDetailSerializer(inspection).data,
            status=status.HTTP_200_OK
        )


class AllInspectionsListView(ListAPIView):
    """
    Admin/manager views all inspections across all vehicles.
    Supports filtering by vehicle, status, inspector.
    """
    permission_classes = [IsAdminOrManager]
    serializer_class = VehicleInspectionListSerializer

    def get_queryset(self):
        qs = VehicleInspection.objects.select_related(
            'vehicle', 'inspected_by'
        ).order_by('-started_at')

        vehicle = self.request.query_params.get('vehicle')
        if vehicle:
            qs = qs.filter(vehicle__id=vehicle)

        insp_status = self.request.query_params.get('status')
        if insp_status:
            qs = qs.filter(status=insp_status)

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
            OpenApiParameter('status', str, description='draft | submitted'),
            OpenApiParameter('inspector', str, description='Filter by employee UUID'),
            OpenApiParameter('has_issue', str, description='true | false'),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)