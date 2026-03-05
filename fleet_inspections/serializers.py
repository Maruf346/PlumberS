from rest_framework import serializers
from .models import *


class InspectionCheckPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = InspectionCheckPhoto
        fields = ['id', 'photo', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class InspectionCheckItemSerializer(serializers.ModelSerializer):
    """Read serializer — includes nested photos."""
    photos = InspectionCheckPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = InspectionCheckItem
        fields = [
            'id', 'category', 'is_ok',
            'issue_detail', 'photos',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InspectionCheckItemWriteSerializer(serializers.ModelSerializer):
    """
    Used when employee saves/updates a single check item.
    issue_detail is required when is_ok=False.
    """
    class Meta:
        model = InspectionCheckItem
        fields = ['category', 'is_ok', 'issue_detail']

    def validate(self, data):
        is_ok = data.get('is_ok', getattr(self.instance, 'is_ok', True))
        issue_detail = data.get('issue_detail', getattr(self.instance, 'issue_detail', ''))
        if not is_ok and not issue_detail.strip():
            raise serializers.ValidationError({
                'issue_detail': 'Issue detail is required when an item is marked as having a problem.'
            })
        # Clear issue_detail if marked OK
        if is_ok:
            data['issue_detail'] = ''
        return data

    def validate_category(self, value):
        valid = [c[0] for c in CheckItemCategory.choices]
        if value not in valid:
            raise serializers.ValidationError(f'Invalid category. Choose from: {valid}')
        return value


# ==================== INSPECTION SERIALIZERS ====================

class VehicleInspectionListSerializer(serializers.ModelSerializer):
    """
    Lightweight — for inspection history list.
    Shows which vehicle, who inspected, when, status, issue count.
    """
    vehicle_name = serializers.CharField(source='vehicle.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    inspected_by_name = serializers.CharField(source='inspected_by.full_name', read_only=True)
    inspected_at = serializers.ReadOnlyField()
    issue_count = serializers.ReadOnlyField()
    completed_items_count = serializers.ReadOnlyField()

    class Meta:
        model = VehicleInspection
        fields = [
            'id', 'vehicle', 'vehicle_name', 'vehicle_plate',
            'inspected_by', 'inspected_by_name',
            'status', 'has_open_issue',
            'issue_count', 'completed_items_count',
            'inspected_at', 'started_at', 'submitted_at'
        ]


class VehicleInspectionDetailSerializer(serializers.ModelSerializer):
    """
    Full detail — includes all check items with nested photos.
    Used for history detail view and current draft retrieval.
    """
    vehicle_name = serializers.CharField(source='vehicle.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    inspected_by_name = serializers.CharField(source='inspected_by.full_name', read_only=True)
    check_items = InspectionCheckItemSerializer(many=True, read_only=True)
    inspected_at = serializers.ReadOnlyField()
    issue_count = serializers.ReadOnlyField()
    completed_items_count = serializers.ReadOnlyField()
    all_categories = serializers.SerializerMethodField()

    class Meta:
        model = VehicleInspection
        fields = [
            'id', 'vehicle', 'vehicle_name', 'vehicle_plate',
            'inspected_by', 'inspected_by_name',
            'status', 'has_open_issue', 'notes',
            'check_items', 'all_categories',
            'issue_count', 'completed_items_count',
            'inspected_at', 'started_at', 'submitted_at', 'updated_at'
        ]

    def get_all_categories(self, obj):
        """
        Returns all 9 categories with their current state.
        Filled ones come from DB; unfilled ones show as pending.
        Useful for mobile app to render the full checklist.
        """
        saved = {item.category: item for item in obj.check_items.all()}
        result = []
        for category_value, category_label in CheckItemCategory.choices:
            if category_value in saved:
                item = saved[category_value]
                result.append({
                    'category': category_value,
                    'label': category_label,
                    'is_ok': item.is_ok,
                    'issue_detail': item.issue_detail,
                    'photos': InspectionCheckPhotoSerializer(
                        item.photos.all(), many=True
                    ).data,
                    'saved': True,
                    'check_item_id': str(item.id)
                })
            else:
                result.append({
                    'category': category_value,
                    'label': category_label,
                    'is_ok': None,
                    'issue_detail': '',
                    'photos': [],
                    'saved': False,
                    'check_item_id': None
                })
        return result


class InspectionStartSerializer(serializers.Serializer):
    """
    Employee starts or resumes an inspection.
    Just needs the vehicle_id.
    """
    vehicle_id = serializers.UUIDField()

    def validate_vehicle_id(self, value):
        from fleets.models import Vehicle
        try:
            Vehicle.objects.get(id=value, is_active=True)
        except Vehicle.DoesNotExist:
            raise serializers.ValidationError('Vehicle not found or inactive.')
        return value


class InspectionSubmitSerializer(serializers.Serializer):
    """
    Employee submits the inspection (DRAFT → SUBMITTED).
    Optional overall notes.
    Validates that at least one check item exists before allowing submit.
    """
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        inspection = self.context.get('inspection')
        if not inspection.check_items.exists():
            raise serializers.ValidationError(
                'Cannot submit an empty inspection. Please fill at least one checklist item.'
            )
        return data