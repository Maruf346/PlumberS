from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CertificateViewSet, AdminCertificateViewSet

router = DefaultRouter()
router.register(r'', CertificateViewSet, basename='certificate')

admin_router = DefaultRouter()
admin_router.register(r'', AdminCertificateViewSet, basename='admin-certificate')

urlpatterns = [
    path('', include(router.urls)),
    path('admin/', include(admin_router.urls)),
]