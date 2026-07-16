import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


class BoardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.board_id = self.scope['url_route']['kwargs']['board_id']
        self.group_name = f'board_{self.board_id}'
        user = self.scope['user']

        if not user.is_authenticated or not await self.is_member(user, self.board_id):
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def board_event(self, event):
        await self.send(text_data=json.dumps(event['payload']))

    @database_sync_to_async
    def is_member(self, user, board_id):
        from boards.models import Board
        return Board.objects.filter(pk=board_id, board_members__user=user).exists()
