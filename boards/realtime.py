from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def broadcast_board_event(board_id, event_type, **payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(
        f'board_{board_id}',
        {
            'type': 'board_event',
            'payload': {'event': event_type, **payload},
        },
    )
