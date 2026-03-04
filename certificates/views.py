from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.exceptions import PermissionDenied
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import Certificate
from .serializers import CertificateSerializer, AdminCertificateSerializer


@extend_schema_view(
    list=extend_schema(summary="List my certificates"),
    retrieve=extend_schema(summary="Retrieve a certificate"),
    create=extend_schema(summary="Add a certificate"),
    update=extend_schema(summary="Update a certificate"),
    partial_update=extend_schema(summary="Partially update a certificate"),
    destroy=extend_schema(summary="Delete a certificate"),
)
class CertificateViewSet(ModelViewSet):
    # Employee CRUD for their own certificates.
    # Users can only access their own records.
    
    serializer_class = CertificateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Certificate.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        # Extra guard: ownership already enforced by get_queryset
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied("You do not own this certificate.")
        instance.delete()


@extend_schema_view(
    list=extend_schema(tags=['admin'], summary="List all certificates"),
    retrieve=extend_schema(tags=['admin'], summary="Retrieve any certificate"),
)
class AdminCertificateViewSet(ReadOnlyModelViewSet):
    # Admin read-only access to all certificates across all users.
    # Supports filtering by user id via ?user=<uuid>.

    serializer_class = AdminCertificateSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = Certificate.objects.select_related('user').all()
        user_id = self.request.query_params.get('user')
        if user_id:
            qs = qs.filter(user__id=user_id)
        return qs