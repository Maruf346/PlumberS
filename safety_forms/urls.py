from django.urls import path
from .views import (
    # Template — shared
    SafetyFormTemplateListView,
    SafetyFormTemplateDetailView,
    # Template — admin
    AdminSafetyFormTemplateCreateView,
    AdminSafetyFormTemplateUpdateView,
    # Fields — admin
    AdminFieldCreateView,
    AdminFieldUpdateView,
    AdminFieldReorderView,
    # Utility
    FieldTypeListView,
)

urlpatterns = [
    # Utility
    path('field-types/', FieldTypeListView.as_view(), name='field-type-list'),

    # Templates — shared read
    path('', SafetyFormTemplateListView.as_view(), name='form-template-list'),
    path('<uuid:id>/', SafetyFormTemplateDetailView.as_view(), name='form-template-detail'),

    # Templates — admin write
    path('create/', AdminSafetyFormTemplateCreateView.as_view(), name='form-template-create'),
    path('<uuid:id>/update/', AdminSafetyFormTemplateUpdateView.as_view(), name='form-template-update'),

    # Fields — admin
    path('<uuid:template_id>/fields/add/', AdminFieldCreateView.as_view(), name='field-create'),
    path('<uuid:template_id>/fields/<uuid:field_id>/', AdminFieldUpdateView.as_view(), name='field-update-delete'),
    path('<uuid:template_id>/fields/reorder/', AdminFieldReorderView.as_view(), name='field-reorder'),
]