from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *


router = DefaultRouter()
router.register(r'', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
    path('fcm/register/', RegisterFCMTokenView.as_view(), name='fcm-register'),
    path('fcm/unregister/', UnregisterFCMTokenView.as_view(), name='fcm-unregister')
]
