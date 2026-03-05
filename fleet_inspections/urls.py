from django.urls import path
from .views import *

urlpatterns = [
    # Admin — all inspections across fleet
    path('', AllInspectionsListView.as_view(), name='all-inspections'),

    # Start or resume
    path('start/', StartOrResumeInspectionView.as_view(), name='inspection-start'),

    # Draft management
    path('<uuid:inspection_id>/items/save/', SaveCheckItemView.as_view(), name='check-item-save'),
    path('<uuid:inspection_id>/items/<uuid:check_item_id>/photos/', CheckItemPhotoUploadView.as_view(), name='check-item-photo-upload'),
    path('<uuid:inspection_id>/items/<uuid:check_item_id>/photos/<uuid:photo_id>/', CheckItemPhotoDeleteView.as_view(), name='check-item-photo-delete'),
    path('<uuid:inspection_id>/submit/', SubmitInspectionView.as_view(), name='inspection-submit'),

    # History — per vehicle
    path('vehicle/<uuid:vehicle_id>/history/', VehicleInspectionHistoryView.as_view(), name='vehicle-inspection-history'),
    path('vehicle/<uuid:vehicle_id>/draft/', MyDraftInspectionView.as_view(), name='my-draft-inspection'),
    path('history/<uuid:id>/', InspectionHistoryDetailView.as_view(), name='inspection-history-detail'),
]