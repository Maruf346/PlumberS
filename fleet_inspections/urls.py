from django.urls import path
from .views import *

urlpatterns = [
    # Admin/manager — all inspections
    path('', AllInspectionsListView.as_view(), name='all-inspections'),

    # Submit — vehicle scoped
    path('vehicle/<uuid:vehicle_id>/submit/', SubmitInspectionView.as_view(), name='inspection-submit'),

    # History — vehicle scoped
    path('vehicle/<uuid:vehicle_id>/history/', VehicleInspectionHistoryView.as_view(), name='vehicle-inspection-history'),

    # Single inspection detail
    path('<uuid:id>/', InspectionDetailView.as_view(), name='inspection-detail'),
]