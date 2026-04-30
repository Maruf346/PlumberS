from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter
import csv

from user.models import EmployeeProfile

from .models import *
from .serializers import *
from user.permissions import IsAdmin, IsAdminOrManager, IsAdminOrManagerOrEmployee


# ==================== FLEET DASHBOARD ====================

class FleetDashboardView(APIView):
    """
    Admin/manager dashboard summary.
    Returns counts by status and total alerts.
    """
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['fleet'],
        summary="Fleet dashboard summary",
        responses={200: FleetDashboardSerializer}
    )
    def get(self, request):
        vehicles = Vehicle.objects.filter(is_active=True)

        # Refresh statuses before building summary
        for v in vehicles:
            v.update_status()

        # Re-query after status updates
        vehicles = Vehicle.objects.filter(is_active=True)

        total = vehicles.count()
        healthy = vehicles.filter(status=VehicleStatus.HEALTHY).count()
        inspection_due = vehicles.filter(status=VehicleStatus.INSPECTION_DUE).count()
        issue_reported = vehicles.filter(status=VehicleStatus.ISSUE_REPORTED).count()
        service_overdue = vehicles.filter(status=VehicleStatus.SERVICE_OVERDUE).count()
        # unassigned = vehicles.filter(assigned_to__isnull=True).count()
        total_alerts = vehicles.exclude(status=VehicleStatus.HEALTHY).count()

        data = {
            'total_fleet': total,
            'healthy': healthy,
            'inspection_due': inspection_due,
            'issue_reported': issue_reported,
            'service_overdue': service_overdue,
            # 'unassigned': unassigned,
            'total_alerts': total_alerts,
        }
        return Response(FleetDashboardSerializer(data).data)


class FleetAlertsView(ListAPIView):
    """
    Returns all vehicles with a non-healthy status.
    Feeds the fleet alerts panel in the dashboard.
    """
    permission_classes = [IsAdminOrManager]
    serializer_class = FleetAlertSerializer

    def get_queryset(self):
        return Vehicle.objects.filter(
            is_active=True
        ).exclude(
            status=VehicleStatus.HEALTHY
        ).order_by('status', 'name')

    @extend_schema(
        tags=['fleet'],
        summary="Fleet alerts",
        description="Returns all vehicles with non-healthy status."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==================== VEHICLE CRUD ====================

class VehicleListView(ListAPIView):
    """
    All authenticated staff can list active vehicles.
    Supports search by name or plate, and filter by status.
    Admin sees all including inactive via ?include_inactive=true.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = VehicleListSerializer

    def get_queryset(self):
        qs = Vehicle.objects.all()

        # Inactive filter — admin only
        if not (
            self.request.user.is_superuser and
            self.request.query_params.get('include_inactive') == 'true'
        ):
            qs = qs.filter(is_active=True)

        # Search
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(plate__icontains=search)
            )

        # Status filter
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Assignment filter
        # assigned = self.request.query_params.get('assigned')
        # if assigned == 'true':
        #     qs = qs.filter(assigned_to__isnull=False)
        # elif assigned == 'false':
        #     qs = qs.filter(assigned_to__isnull=True)

        return qs.order_by('name')

    @extend_schema(
        tags=['fleet'],
        summary="List vehicles",
        parameters=[
            OpenApiParameter('search', str, description='Search by name or plate'),
            OpenApiParameter('status', str, description='Filter by status value'),
            # OpenApiParameter('assigned', str, description='true / false'),
            OpenApiParameter('include_inactive', str, description='Admin only: true to include inactive'),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class VehicleDetailView(RetrieveAPIView):
    """Any authenticated staff retrieves full vehicle detail."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = VehicleDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Vehicle.objects.all()
        return Vehicle.objects.filter(is_active=True)

    @extend_schema(tags=['fleet'], summary="Retrieve vehicle detail")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminVehicleCreateView(APIView):
    """Admin adds a new vehicle to the fleet."""
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=['fleet'],
        summary="Create vehicle",
        request=VehicleWriteSerializer,
        responses={201: VehicleDetailSerializer}
    )
    def post(self, request):
        serializer = VehicleWriteSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        vehicle = serializer.save()
        return Response(
            {
                'message': 'Vehicle added to fleet.',
                'data': VehicleDetailSerializer(vehicle, context={'request': request}).data
            },
            status=status.HTTP_201_CREATED
        )


class AdminVehicleUpdateView(APIView):
    """Admin updates or deletes a vehicle."""
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self, id):
        return get_object_or_404(Vehicle, id=id)

    @extend_schema(
        tags=['fleet'],
        summary="Update vehicle",
        request=VehicleWriteSerializer,
        responses={200: VehicleDetailSerializer}
    )
    def patch(self, request, id):
        vehicle = self.get_object(id)
        serializer = VehicleWriteSerializer(
            vehicle, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        vehicle = serializer.save()
        return Response(
            {
                'message': 'Vehicle updated.',
                'data': VehicleDetailSerializer(vehicle, context={'request': request}).data
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(tags=['fleet'], summary="Delete vehicle", responses={204: None})
    def delete(self, request, id):
        vehicle = self.get_object(id)
        vehicle.delete()
        return Response({'message': 'Vehicle removed from fleet.'}, status=status.HTTP_204_NO_CONTENT)


# ==================== MAINTENANCE ====================

class MaintenanceListView(ListAPIView):
    """List maintenance records for a specific vehicle."""
    permission_classes = [IsAdminOrManager]
    serializer_class = MaintenanceScheduleSerializer

    def get_queryset(self):
        vehicle_id = self.kwargs.get('vehicle_id')
        qs = MaintenanceSchedule.objects.filter(vehicle__id=vehicle_id)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by('-scheduled_date')

    @extend_schema(
        tags=['fleet'],
        summary="List maintenance records for a vehicle",
        parameters=[
            OpenApiParameter('status', str, description='Filter by maintenance status')
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminMaintenanceCreateView(APIView):
    """Admin schedules a maintenance for a vehicle."""
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['fleet'],
        summary="Schedule maintenance",
        request=MaintenanceScheduleWriteSerializer,
        responses={201: MaintenanceScheduleSerializer}
    )
    def post(self, request, vehicle_id):
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)
        serializer = MaintenanceScheduleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(vehicle=vehicle)
        return Response(
            {
                'message': 'Maintenance scheduled.',
                'data': MaintenanceScheduleSerializer(record).data
            },
            status=status.HTTP_201_CREATED
        )


class AdminMaintenanceUpdateView(APIView):
    """Admin updates a maintenance record (e.g. mark as completed)."""
    permission_classes = [IsAdmin]

    def get_object(self, vehicle_id, maintenance_id):
        return get_object_or_404(
            MaintenanceSchedule,
            id=maintenance_id,
            vehicle__id=vehicle_id
        )

    @extend_schema(
        tags=['fleet'],
        summary="Update maintenance record",
        request=MaintenanceScheduleWriteSerializer,
        responses={200: MaintenanceScheduleSerializer}
    )
    def patch(self, request, vehicle_id, maintenance_id):
        record = self.get_object(vehicle_id, maintenance_id)
        serializer = MaintenanceScheduleWriteSerializer(
            record, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(
            {
                'message': 'Maintenance record updated.',
                'data': MaintenanceScheduleSerializer(record).data
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(tags=['fleet'], summary="Delete maintenance record", responses={204: None})
    def delete(self, request, vehicle_id, maintenance_id):
        record = self.get_object(vehicle_id, maintenance_id)
        record.delete()
        return Response({'message': 'Maintenance record deleted.'}, status=status.HTTP_204_NO_CONTENT)


# ==================== FLEET REPORT (CSV download) ====================

class FleetReportDownloadView(APIView):
    """
    Admin downloads a CSV fleet report.
    PDF generation will be added in the reports phase.
    """
    permission_classes = [IsAdmin]

    @extend_schema(
        tags=['fleet'],
        summary="Download fleet report (CSV)",
        description="Returns a CSV file with all vehicle statuses and maintenance info."
    )
    def get(self, request):
        vehicles = Vehicle.objects.filter(is_active=True)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="fleet_report.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Name', 'Plate', 'Status', 'Make', 'Model', 'Year',
            'Assigned To', 'Current Odometer (km)', 'Next Service (km)',
            'KM Until Service', 'Last Inspection', 'Notes'
        ])

        for v in vehicles:
            writer.writerow([
                v.name,
                v.plate,
                v.get_status_display(),
                v.make,
                v.model_name,
                v.year or '',
                # v.assigned_to.full_name if v.assigned_to else 'Unassigned',
                v.current_odometer_km or '',
                v.next_service_km or '',
                v.km_until_service if v.km_until_service is not None else '',
                v.last_inspection_date.strftime('%Y-%m-%d %H:%M') if v.last_inspection_date else 'Never',
                v.notes,
            ])

        return response
    
    
class EmployeeAddFuelView(APIView):
    """
    POST /api/fleets/fuel/add/
    Employee adds a fuel log for their assigned vehicle.
    Only works if the employee has an assigned vehicle on their profile.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=['fleets-fuel'],
        summary="Add fuel log (employee)",
        description=(
            "Employee submits a fuel addition for their assigned vehicle. "
            "Vehicle is automatically determined from the employee profile — "
            "employee cannot choose a different vehicle."
        ),
        request=FuelLogCreateSerializer,
        responses={201: FuelLogSerializer},
    )
    def post(self, request):
        serializer = FuelLogCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        fuel_log = serializer.save()
        return Response(
            {
                'message': 'Fuel log added successfully.',
                'data': FuelLogSerializer(fuel_log, context={'request': request}).data,
            },
            status=status.HTTP_201_CREATED
        )


class AdminVehicleFuelHistoryView(ListAPIView):
    """
    GET /api/fleets/{vehicle_id}/fuel-history/
    Admin/manager views full fuel log history for a specific vehicle.
    Returns all entries ordered by date descending with full details per entry.
    """
    permission_classes = [IsAdminOrManager]
    serializer_class = FuelLogSerializer

    def get_queryset(self):
        return FuelLog.objects.filter(
            vehicle__id=self.kwargs['vehicle_id']
        ).select_related('added_by', 'vehicle').order_by('-date', '-created_at')

    @extend_schema(
        tags=['fleets-fuel'],
        summary="Vehicle fuel history (admin)",
        description="Full fuel log history for a specific vehicle. All entries with complete details."
    )
    def get(self, request, *args, **kwargs):
        # Verify vehicle exists
        get_object_or_404(Vehicle, id=self.kwargs['vehicle_id'])
        return super().get(request, *args, **kwargs)


class VehicleAssignedEmployeeView(APIView):
    """
    GET /api/fleets/{vehicle_id}/assigned-employee/
    Returns the employee currently assigned to a vehicle.
    Returns null if no employee is assigned.
    """
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['fleets'],
        summary="Get assigned employee for a vehicle",
        description=(
            "Returns the employee currently assigned to the given vehicle. "
            "Returns null if no employee is currently assigned."
        ),
        responses={200: VehicleAssignedEmployeeSerializer},
    )
    def get(self, request, vehicle_id):
        vehicle = get_object_or_404(Vehicle, id=vehicle_id)

        try:
            profile = EmployeeProfile.objects.select_related('user').get(
                assigned_vehicle=vehicle,
                user__is_active=True
            )
        except EmployeeProfile.DoesNotExist:
            return Response({
                'vehicle_id': str(vehicle.id),
                'vehicle_name': vehicle.name,
                'assigned_employee': None,
            }, status=status.HTTP_200_OK)

        return Response({
            'vehicle_id': str(vehicle.id),
            'vehicle_name': vehicle.name,
            'assigned_employee': VehicleAssignedEmployeeSerializer(
                profile, context={'request': request}
            ).data,
        }, status=status.HTTP_200_OK)