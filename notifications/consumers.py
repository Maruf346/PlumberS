import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        token = self.scope['query_string'].decode().split('token=')[-1]
        # FE: ws://localhost:8000/ws/notifications/?token=eyJ0eXAiOiJK...
        
        # Authenticate user
        self.user = await self.get_user_from_token(token)
        
        if self.user and not isinstance(self.user, AnonymousUser):
            # Create user-specific group
            self.group_name = f'user_{self.user.id}'
            
            # Join group
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            
            # Send connection success message
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to notification service'
            }))
        else:
            # Reject connection
            await self.close()
            
    async def disconnect(self, close_code):
        # Leave group
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
            
    async def receive(self, text_data):
        data = json.loads(text_data)
        
        if data.get('action') == 'mark_read':
            notification_id = data.get('notification_id')
            await self.mark_notification_read(notification_id)
            
    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification_type': event.get('notification_type'),
            'title': event['title'],
            'body': event['body'],
            'data': event.get('data', {}),
            'priority': event.get('priority', 'normal'),
            'timestamp': event.get('timestamp')
        }))
        
    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            UntypedToken(token)
            from rest_framework_simplejwt.authentication import JWTAuthentication
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            return jwt_auth.get_user(validated_token)
        except (InvalidToken, TokenError):
            return AnonymousUser()
        
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        from notifications.models import Notification
        from django.utils import timezone
        
        try:
            notification = Notification.objects.get(id=notification_id, user=self.user)
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
        except Notification.DoesNotExist:
            pass