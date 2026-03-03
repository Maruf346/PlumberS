from django.shortcuts import render
from rest_framework import status, viewsets, views
from .serializers import *
from .models import Notification
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
import logging
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view



logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List notifications",
        description="Get all notifications for the authenticated user, with optional filtering by read status, type, and priority."
    ),
    retrieve=extend_schema(
        summary="Get a single notification",
        description="Retrieve the details of a specific notification by its ID."
    ),
    mark_read=extend_schema(
        summary="Mark a notification as read",
        description="Mark a single notification as read. POST /api/notifications/{id}/mark-read/"
    ),
    mark_all_read=extend_schema(
        summary="Mark all notifications as read",
        description="Mark all notifications for the authenticated user as read."
    ),
    unread_count=extend_schema(
        summary="Get unread notifications count",
        description="Return the total number of unread notifications for the authenticated user."
    ),
    clear_read=extend_schema(
        summary="Clear read notifications",
        description="Delete all notifications that have been marked as read for the authenticated user."
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
        # POST /api/notifications/{id}/mark-read/
        notification = self.get_object()
        
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
            
        serializer = self.get_serializer(notification)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
        
        return Response({
            'message': f'{count} notification(s) marked as read',
            'count': count
        }, status=status.HTTP_200_OK)
        
    
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        
        return Response({
            'unread_count': count
        }, status=status.HTTP_200_OK)
        
        
    @action(detail=False, methods=['delete'], url_path='clear-read')
    def clear_read(self, request):
        deleted_count, _ = Notification.objects.filter(user=request.user, is_read=True).delete()
        
        return Response({
            'message': f'{deleted_count} notification(s) deleted',
            'deleted_count': deleted_count
        }, status=status.HTTP_200_OK)
        
      
@extend_schema(
    request=FCMTokenSerializer,
    responses={201: OpenApiResponse(description="FCM token registered successfully")},
    summary="Register FCM token",
    description="Register a device token to receive push notifications via FCM."
)
@method_decorator(ratelimit(key='user', rate='30/h', method='POST', block=True), name='dispatch')
class RegisterFCMTokenView(views.APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FCMTokenSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        logger.info(f'FCM token registered for user {request.user.email}')
        
        return Response({
            'message': 'FCM token registered successfully'
        }, status=status.HTTP_201_CREATED)
        
    
@extend_schema(
    request=FCMTokenDeleteSerializer,
    responses={
        200: OpenApiResponse(description="FCM token unregistered successfully"),
        404: OpenApiResponse(description="Token not found")
    },
    summary="Unregister FCM token",
    description="Remove a device token to stop receiving push notifications."
)  
@method_decorator(ratelimit(key='user', rate='20/h', method='POST', block=True), name='dispatch')
class UnregisterFCMTokenView(views.APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FCMTokenDeleteSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        
        deleted_count = FCMToken.objects.filter(user=request.user, token=token).delete()[0]
        
        if deleted_count > 0:
            logger.info(f"FCM token unregistered for user {request.user.email}")
            return Response(
                {'message': 'FCM token unregistered successfully'},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {'error': 'Token not found'},
                status=status.HTTP_404_NOT_FOUND
            )