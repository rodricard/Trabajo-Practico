from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification


def broadcast_notification(user_id, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        f'user_{user_id}',
        {
            'type': 'user_event',
            'payload': {'event': 'notification', **payload},
        },
    )


def notify_user(user, title, link=''):
    notification = Notification.objects.create(user=user, title=title, link=link)
    broadcast_notification(user.id, {
        'id': notification.id,
        'title': notification.title,
        'link': notification.link,
        'created_at': notification.created_at.isoformat(),
    })
    return notification
