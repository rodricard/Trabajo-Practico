import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


# En memoria: board_id (str) -> {channel_name: username}. Vive dentro del
# proceso del servidor, alcanza para mostrar quién está viendo el tablero.
_board_viewers = {}


class BoardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.board_id = self.scope['url_route']['kwargs']['board_id']
        self.group_name = f'board_{self.board_id}'
        user = self.scope['user']

        if not user.is_authenticated or not await self.is_member(user, self.board_id):
            await self.close()
            return

        self.username = user.username
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        _board_viewers.setdefault(self.board_id, {})[self.channel_name] = self.username
        await self._broadcast_presence()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        if hasattr(self, 'board_id') and self.board_id in _board_viewers:
            _board_viewers[self.board_id].pop(self.channel_name, None)
            await self._broadcast_presence()

    async def board_event(self, event):
        await self.send(text_data=json.dumps(event['payload']))

    async def _broadcast_presence(self):
        viewers = sorted(set(_board_viewers.get(self.board_id, {}).values()))
        await self.channel_layer.group_send(
            self.group_name,
            {'type': 'board_event', 'payload': {'event': 'presence_update', 'viewers': viewers}},
        )

    @database_sync_to_async
    def is_member(self, user, board_id):
        from boards.models import Board
        return Board.objects.filter(pk=board_id, board_members__user=user).exists()
