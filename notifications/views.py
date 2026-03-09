from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from drf_spectacular.utils import extend_schema, extend_schema_view
import logging

from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        tags=['notifications'],
        summary="List notifications",
        description="Get all notifications for the authenticated user."
    ),
    retrieve=extend_schema(
        tags=['notifications'],
        summary="Get a single notification"
    ),
    mark_read=extend_schema(
        tags=['notifications'],
        summary="Mark notification as read"
    ),
    mark_all_read=extend_schema(
        tags=['notifications'],
        summary="Mark all notifications as read"
    ),
    unread_count=extend_schema(
        tags=['notifications'],
        summary="Get unread count"
    ),
    clear_read=extend_schema(
        tags=['notifications'],
        summary="Delete all read notifications"
    ),
)
@method_decorator(ratelimit(key='user', rate='200/h', method='GET', block=False), name='dispatch')
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    filterset_fields = ['is_read', 'notification_type', 'priority']
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        count = Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({'message': f'{count} notification(s) marked as read.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'], url_path='clear-read')
    def clear_read(self, request):
        deleted_count, _ = Notification.objects.filter(
            user=request.user, is_read=True
        ).delete()
        return Response({'deleted_count': deleted_count}, status=status.HTTP_200_OK)