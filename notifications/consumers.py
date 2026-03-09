import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        token = self._extract_token()
        self.user = await self.get_user_from_token(token)

        if self.user and not isinstance(self.user, AnonymousUser):
            self.group_name = f'user_{self.user.id}'
            await self.channel_layer.group_add(self.group_name, self.channel_name)
            await self.accept()
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Connected to notification service',
            }))
            # Send unread count on connect
            count = await self.get_unread_count()
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': count,
            }))
        else:
            await self.close()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        action = data.get('action')

        if action == 'mark_read':
            notification_id = data.get('notification_id')
            if notification_id:
                await self.mark_notification_read(notification_id)
                count = await self.get_unread_count()
                await self.send(text_data=json.dumps({
                    'type': 'unread_count',
                    'count': count,
                }))

        elif action == 'mark_all_read':
            await self.mark_all_read()
            await self.send(text_data=json.dumps({
                'type': 'unread_count',
                'count': 0,
            }))

    async def notification_message(self, event):
        """Called when a new notification is pushed to this user's group."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification_id': event.get('notification_id'),
            'notification_type': event.get('notification_type'),
            'title': event['title'],
            'body': event['body'],
            'data': event.get('data', {}),
            'priority': event.get('priority', 'normal'),
            'created_at': event.get('created_at'),
        }))
        # Also send updated unread count after new notification
        count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': count,
        }))

    # ==================== HELPERS ====================

    def _extract_token(self):
        query = self.scope.get('query_string', b'').decode()
        for part in query.split('&'):
            if part.startswith('token='):
                return part.split('token=')[-1]
        return ''

    @database_sync_to_async
    def get_user_from_token(self, token):
        if not token:
            return AnonymousUser()
        try:
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
            n = Notification.objects.get(id=notification_id, user=self.user)
            if not n.is_read:
                n.is_read = True
                n.read_at = timezone.now()
                n.save()
        except Notification.DoesNotExist:
            pass

    @database_sync_to_async
    def mark_all_read(self):
        from notifications.models import Notification
        from django.utils import timezone
        Notification.objects.filter(
            user=self.user, is_read=False
        ).update(is_read=True, read_at=timezone.now())

    @database_sync_to_async
    def get_unread_count(self):
        from notifications.models import Notification
        return Notification.objects.filter(user=self.user, is_read=False).count()