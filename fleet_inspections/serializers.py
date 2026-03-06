from rest_framework import serializers
from .models import *


class InspectionCheckPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = InspectionCheckPhoto
        fields = ['id', 'photo', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']


class InspectionCheckItemSerializer(serializers.ModelSerializer):
    """Read serializer — nested photos included."""
    photos = InspectionCheckPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = InspectionCheckItem
        fields = ['id', 'category', 'is_ok', 'issue_detail', 'photos', 'created_at']
        read_only_fields = ['id', 'created_at']


class CheckItemSubmitSerializer(serializers.Serializer):
    """
    Represents one checklist item inside the submission payload.
    Photos are handled separately via request.FILES in the view
    using a keyed naming convention: items[<index>][photos][].
    """
    category = serializers.ChoiceField(choices=CheckItemCategory.choices)
    is_ok = serializers.BooleanField()
    issue_detail = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        if not data['is_ok'] and not data.get('issue_detail', '').strip():
            raise serializers.ValidationError({
                'issue_detail': f"Issue detail is required for "
                                f"'{data['category']}' when marked as having a problem."
            })
        if data['is_ok']:
            data['issue_detail'] = ''
        return data


class InspectionSubmitSerializer(serializers.Serializer):
    """
    Top-level serializer for the full inspection submission.
    items is a list of CheckItemSubmitSerializer.
    At least one item must be provided.
    Duplicate categories are rejected.
    """
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    items = CheckItemSubmitSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError(
                'At least one checklist item must be submitted.'
            )
        categories = [item['category'] for item in value]
        if len(categories) != len(set(categories)):
            raise serializers.ValidationError(
                'Duplicate categories found. Each category can only appear once.'
            )
        return value


# ==================== READ SERIALIZERS ====================

class VehicleInspectionListSerializer(serializers.ModelSerializer):
    """Lightweight — for history list view."""
    vehicle_name = serializers.CharField(source='vehicle.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    inspected_by_name = serializers.CharField(source='inspected_by.full_name', read_only=True)
    issue_count = serializers.ReadOnlyField()
    completed_items_count = serializers.ReadOnlyField()

    class Meta:
        model = VehicleInspection
        fields = [
            'id', 'vehicle', 'vehicle_name', 'vehicle_plate',
            'inspected_by', 'inspected_by_name',
            'has_open_issue', 'issue_count', 'completed_items_count',
            'notes', 'inspected_at'
        ]


class VehicleInspectionDetailSerializer(serializers.ModelSerializer):
    """Full detail — all check items with nested photos."""
    vehicle_name = serializers.CharField(source='vehicle.name', read_only=True)
    vehicle_plate = serializers.CharField(source='vehicle.plate', read_only=True)
    inspected_by_name = serializers.CharField(source='inspected_by.full_name', read_only=True)
    check_items = InspectionCheckItemSerializer(many=True, read_only=True)
    issue_count = serializers.ReadOnlyField()
    completed_items_count = serializers.ReadOnlyField()

    class Meta:
        model = VehicleInspection
        fields = [
            'id', 'vehicle', 'vehicle_name', 'vehicle_plate',
            'inspected_by', 'inspected_by_name',
            'has_open_issue', 'notes',
            'check_items', 'issue_count', 'completed_items_count',
            'inspected_at', 'updated_at'
        ]