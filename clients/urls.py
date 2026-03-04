from django.urls import path
from .views import *

urlpatterns = [
    # Admin only
    path('', AdminClientListView.as_view(), name='admin-client-list'),
    path('create/', ClientCreateView.as_view(), name='client-create'),
    path('<uuid:id>/', ClientUpdateView.as_view(), name='client-update-delete'),

    # All authenticated staff
    path('list/', ClientListView.as_view(), name='client-list'),
    path('detail/<uuid:id>/', ClientDetailView.as_view(), name='client-detail'),
]