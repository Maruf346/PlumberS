from rest_framework import serializers
from .models import SafetyFormTemplate, SafetyFormField, FieldType


# ==================== FIELD SERIALIZERS ====================

class SafetyFormFieldSerializer(serializers.ModelSerializer):
    """
    Used when reading a field.
    options_list exposes the comma-separated string as a clean list.
    """
    options_list = serializers.ReadOnlyField()

    class Meta:
        model = SafetyFormField
        fields = [
            'id', 'label', 'field_type',
            'options', 'options_list',
            'is_required', 'order', 'helper_text',
            'created_at', 'updated_at'
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
            # Auto-clear options for non-select types rather than raising error
            data['options'] = ''

        return data


class SafetyFormFieldWriteSerializer(serializers.ModelSerializer):
    """
    Used when admin creates/updates a field.
    template is set via the URL/view context, not from request body.
    """
    options_list = serializers.ReadOnlyField()

    class Meta:
        model = SafetyFormField
        fields = [
            'id', 'label', 'field_type',
            'options', 'options_list',
            'is_required', 'order', 'helper_text',
            'created_at', 'updated_at'
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

    def validate_order(self, value):
        # Check uniqueness within the same template, excluding self on update
        template = self.context.get('template')
        qs = SafetyFormField.objects.filter(template=template, order=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f'A field with order {value} already exists in this template. '
                'Use the reorder endpoint to rearrange fields.'
            )
        return value


# ==================== TEMPLATE SERIALIZERS ====================

class SafetyFormTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight — for list views. Does not nest all fields."""
    field_count = serializers.SerializerMethodField()

    class Meta:
        model = SafetyFormTemplate
        fields = [
            'id', 'name', 'description',
            'is_active', 'field_count',
            'created_at', 'updated_at'
        ]

    def get_field_count(self, obj):
        return obj.fields.count()


class SafetyFormTemplateDetailSerializer(serializers.ModelSerializer):
    """
    Full detail — nests all fields ordered by position.
    Used for retrieve, and for employees viewing a form before filling.
    """
    fields = SafetyFormFieldSerializer(many=True, read_only=True)

    class Meta:
        model = SafetyFormTemplate
        fields = [
            'id', 'name', 'description',
            'is_active', 'fields',
            'created_at', 'updated_at'
        ]


class SafetyFormTemplateWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates or updates a template (name, description, is_active).
    Fields are managed separately via their own endpoints.
    """
    class Meta:
        model = SafetyFormTemplate
        fields = ['id', 'name', 'description', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_name(self, value):
        value = value.strip()
        qs = SafetyFormTemplate.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A form template with this name already exists.')
        return value


class FieldReorderSerializer(serializers.Serializer):
    """
    Accepts a list of {id, order} pairs to bulk-reorder fields.
    e.g. [{"id": "uuid", "order": 1}, {"id": "uuid2", "order": 2}]
    """
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