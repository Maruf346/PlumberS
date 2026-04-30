from rest_framework import serializers
from django.utils import timezone
from .models import *
from user.models import User


# class AssignedEmployeeSerializer(serializers.ModelSerializer):
#     """Minimal employee info shown inside vehicle responses."""
#     class Meta:
#         model = User
#         fields = ['id', 'full_name', 'email', 'phone', 'profile_picture']


# ==================== VEHICLE SERIALIZERS ====================

class VehicleListSerializer(serializers.ModelSerializer):
    """
    Lightweight — used in list views and dashboard fleet summary.
    Shows key status info without heavy nesting.
    """
    # assigned_to = AssignedEmployeeSerializer(read_only=True)
    last_inspection_date = serializers.ReadOnlyField()
    km_until_service = serializers.ReadOnlyField()
    is_service_overdue = serializers.ReadOnlyField()

    class Meta:
        model = Vehicle
        fields = [
            'id', 'name', 'plate', 'picture', 'status',
            'last_inspection_date',
            'current_odometer_km', 'next_service_km',
            'km_until_service', 'is_service_overdue',
            'registration_due', 'service_due',
            'is_active', 'created_at'
        ]


class VehicleDetailSerializer(serializers.ModelSerializer):
    """Full detail — used in retrieve view."""
    # assigned_to = AssignedEmployeeSerializer(read_only=True)
    last_inspection_date = serializers.ReadOnlyField()
    km_until_service = serializers.ReadOnlyField()
    is_service_overdue = serializers.ReadOnlyField()
    upcoming_maintenance = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            'id', 'name', 'plate', 'picture', 'status',
            'make', 'model_name', 'year', 'notes',
            # 'assigned_to',
            'current_odometer_km', 'next_service_km',
            'km_until_service', 'is_service_overdue',
            'last_inspection_date', 'upcoming_maintenance',
            'registration_due', 'service_due',
            'is_active', 'created_at', 'updated_at'
        ]

    def get_upcoming_maintenance(self, obj):
        upcoming = obj.maintenance_schedules.filter(
            status=MaintenanceStatus.SCHEDULED
        ).order_by('scheduled_date').first()
        if upcoming:
            return MaintenanceScheduleSerializer(upcoming).data
        return None


class VehicleWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates or updates a vehicle.
    assigned_to accepts a User UUID — validated to be an employee only.
    """
    # assigned_to_id = serializers.UUIDField(
    #     required=False,
    #     allow_null=True,
    #     write_only=True,
    #     help_text="UUID of the employee to assign. Pass null to unassign."
    # )

    class Meta:
        model = Vehicle
        fields = [
            'name', 'plate', 'picture',
            'make', 'model_name', 'year',
            'current_odometer_km', 'next_service_km',
            'registration_due', 'service_due',
            'notes', 'is_active' # 'assigned_to_id',
        ]

    # def validate_assigned_to_id(self, value):
    #     if value is None:
    #         return value
    #     try:
    #         user = User.objects.get(id=value)
    #     except User.DoesNotExist:
    #         raise serializers.ValidationError('User not found.')
    #     if user.is_staff or user.is_superuser:
    #         raise serializers.ValidationError(
    #             'Vehicles can only be assigned to employees, not managers or admins.'
    #         )
    #     return value

    def validate_plate(self, value):
        value = value.upper().strip()
        qs = Vehicle.objects.filter(plate__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A vehicle with this plate already exists.')
        return value

    def validate(self, data):
        current = data.get('current_odometer_km', getattr(self.instance, 'current_odometer_km', None))
        next_service = data.get('next_service_km', getattr(self.instance, 'next_service_km', None))
        if current and next_service and next_service <= current:
            raise serializers.ValidationError({
                'next_service_km': 'Next service km must be greater than current odometer reading.'
            })
        return data

    def create(self, validated_data):
        return Vehicle.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        instance.update_status()
        return instance


# ==================== MAINTENANCE SERIALIZERS ====================

class MaintenanceScheduleSerializer(serializers.ModelSerializer):
    """Read serializer for maintenance records."""
    vehicle_name = serializers.CharField(source='vehicle.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)

    class Meta:
        model = MaintenanceSchedule
        fields = [
            'id', 'vehicle', 'vehicle_name', 'vehicle_plate',
            'scheduled_date', 'description', 'status',
            'odometer_at_service', 'cost', 'performed_by',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'vehicle_name', 'vehicle_plate', 'created_at', 'updated_at']


class MaintenanceScheduleWriteSerializer(serializers.ModelSerializer):
    """Admin creates or updates a maintenance record."""

    class Meta:
        model = MaintenanceSchedule
        fields = [
            'scheduled_date', 'description', 'status',
            'odometer_at_service', 'cost', 'performed_by', 'notes'
        ]

    def validate_scheduled_date(self, value):
        # Allow past dates for logging completed maintenance, just not required future
        return value

    def update(self, instance, validated_data):
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        instance.save()
        # If completed, update vehicle odometer if provided
        if (
            instance.status == MaintenanceStatus.COMPLETED and
            instance.odometer_at_service
        ):
            vehicle = instance.vehicle
            vehicle.current_odometer_km = instance.odometer_at_service
            vehicle.save()
            vehicle.update_status()
        return instance


# ==================== DASHBOARD / ALERT SERIALIZERS ====================

class FleetDashboardSerializer(serializers.Serializer):
    """
    Summary counts for the admin fleet dashboard.
    Built manually in the view from queryset aggregations.
    """
    total_fleet = serializers.IntegerField()
    healthy = serializers.IntegerField()
    inspection_due = serializers.IntegerField()
    issue_reported = serializers.IntegerField()
    service_overdue = serializers.IntegerField()
    # unassigned = serializers.IntegerField()
    total_alerts = serializers.IntegerField()


class FleetAlertSerializer(serializers.ModelSerializer):
    """
    Per-vehicle alert shown in the fleet alerts panel.
    Only vehicles with non-healthy status appear here.
    """
    # assigned_to = AssignedEmployeeSerializer(read_only=True)
    last_inspection_date = serializers.ReadOnlyField()

    class Meta:
        model = Vehicle
        fields = [
            'id', 'name', 'plate', 'status',
            'last_inspection_date', # 'assigned_to', 
            'km_until_service', 'is_service_overdue'
        ]
        
        
class FuelLogSerializer(serializers.ModelSerializer):
    """Read serializer — used in admin fuel history list."""
    added_by_name = serializers.CharField(source='added_by.full_name', read_only=True)
    vehicle_name = serializers.CharField(source='vehicle.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)

    class Meta:
        model = FuelLog
        fields = [
            'id', 'vehicle', 'vehicle_name', 'vehicle_plate',
            'added_by', 'added_by_name',
            'date', 'litres', 'cost', 'odometer_km',
            'receipt_photo', 'notes', 'created_at',
        ]
        read_only_fields = ['id', 'vehicle', 'added_by', 'vehicle_name',
                            'vehicle_plate', 'added_by_name', 'created_at']


class FuelLogCreateSerializer(serializers.ModelSerializer):
    """Employee submits fuel addition for their assigned vehicle."""

    class Meta:
        model = FuelLog
        fields = ['date', 'litres', 'cost', 'odometer_km', 'receipt_photo', 'notes']

    def validate(self, data):
        user = self.context['request'].user
        # Check employee has an assigned vehicle
        try:
            profile = user.employee_profile
        except Exception:
            raise serializers.ValidationError(
                'You do not have an employee profile.'
            )
        if not profile.assigned_vehicle:
            raise serializers.ValidationError(
                'You do not have an assigned vehicle. Contact your admin.'
            )
        return data

    def create(self, validated_data):
        user = self.context['request'].user
        vehicle = user.employee_profile.assigned_vehicle
        return FuelLog.objects.create(
            vehicle=vehicle,
            added_by=user,
            **validated_data
        )


class VehicleAssignedEmployeeSerializer(serializers.Serializer):
    """
    Returns the employee currently assigned to a vehicle.
    Used by admin fleet page to show assigned employee per vehicle.
    """
    employee_id = serializers.UUIDField(source='user.id')
    full_name = serializers.CharField(source='user.full_name')
    email = serializers.CharField(source='user.email')
    phone = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    employee_profile_id = serializers.UUIDField(source='id')
    primary_skill = serializers.CharField()
    employee_id_number = serializers.CharField(source='employee_id')

    def get_phone(self, obj):
        return str(obj.user.phone) if obj.user.phone else None

    def get_profile_picture(self, obj):
        request = self.context.get('request')
        pic = obj.user.profile_picture
        if pic and request:
            return request.build_absolute_uri(pic.url)
        return None