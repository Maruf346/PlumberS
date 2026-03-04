from django.urls import path
from .views import (
    # Dashboard
    FleetDashboardView,
    FleetAlertsView,
    # Vehicles — shared
    VehicleListView,
    VehicleDetailView,
    # Vehicles — admin
    AdminVehicleCreateView,
    AdminVehicleUpdateView,
    # Maintenance — shared
    MaintenanceListView,
    # Maintenance — admin
    AdminMaintenanceCreateView,
    AdminMaintenanceUpdateView,
    # Report
    FleetReportDownloadView,
)

urlpatterns = [
    # Dashboard & alerts
    path('dashboard/', FleetDashboardView.as_view(), name='fleet-dashboard'),
    path('alerts/', FleetAlertsView.as_view(), name='fleet-alerts'),

    # Vehicle CRUD
    path('', VehicleListView.as_view(), name='vehicle-list'),
    path('create/', AdminVehicleCreateView.as_view(), name='vehicle-create'),
    path('<uuid:id>/', VehicleDetailView.as_view(), name='vehicle-detail'),
    path('<uuid:id>/update/', AdminVehicleUpdateView.as_view(), name='vehicle-update-delete'),

    # Maintenance
    path('<uuid:vehicle_id>/maintenance/', MaintenanceListView.as_view(), name='maintenance-list'),
    path('<uuid:vehicle_id>/maintenance/add/', AdminMaintenanceCreateView.as_view(), name='maintenance-create'),
    path('<uuid:vehicle_id>/maintenance/<uuid:maintenance_id>/', AdminMaintenanceUpdateView.as_view(), name='maintenance-update-delete'),

    # Report
    path('report/download/', FleetReportDownloadView.as_view(), name='fleet-report'),
]