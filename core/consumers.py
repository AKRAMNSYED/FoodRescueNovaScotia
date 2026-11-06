import uuid

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.utils import timezone

from .models import MultiplayerPlayer, MultiplayerPresence
from .multiplayer import (
    PRESENCE_TIMEOUT,
    claim_bingo,
    get_world_snapshot,
    perform_action,
    update_presence,
)


WORLD_GROUP = 'multiplayer-world'


class MultiplayerConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        if not settings.MULTIPLAYER_AVAILABLE:
            await self.close(code=1013)
            return

        player = await self.get_session_player()
        if player is None:
            await self.close(code=4401)
            return

        self.player_id = player.pk
        self.player_name = player.name
        self.avatar = player.avatar
        self.custom_character = player.custom_character
        self.connection_id = uuid.uuid4()
        await self.create_presence()
        await self.channel_layer.group_add(WORLD_GROUP, self.channel_name)
        await self.accept()
        await self.send_json({
            'type': 'snapshot',
            **await self.get_snapshot(),
        })
        await self.channel_layer.group_send(
            WORLD_GROUP,
            {
                'type': 'presence.joined',
                'player': await self.presence_payload(),
            },
        )

    async def disconnect(self, close_code):
        if not hasattr(self, 'connection_id'):
            return
        await self.delete_presence()
        await self.channel_layer.group_discard(WORLD_GROUP, self.channel_name)
        remaining = await self.latest_presence()
        if remaining:
            await self.channel_layer.group_send(
                WORLD_GROUP,
                {'type': 'presence.joined', 'player': remaining},
            )
        else:
            await self.channel_layer.group_send(
                WORLD_GROUP,
                {'type': 'presence.left', 'player_id': self.player_id},
            )

    async def receive_json(self, content, **kwargs):
        if not isinstance(content, dict):
            return
        message_type = content.get('type')
        if message_type == 'sync':
            await self.send_json({'type': 'snapshot', **await self.get_snapshot()})
        elif message_type == 'move':
            x = content.get('x')
            player = await self.update_player_position(x)
            if player:
                await self.channel_layer.group_send(
                    WORLD_GROUP,
                    {'type': 'player.moved', 'player': player},
                )
        elif message_type == 'action':
            result = await self.perform_player_action(content.get('action'))
            await self.send_json({'type': 'action_result', **result})
            if result.get('ok'):
                await self.broadcast_player_update(result['player'])
        elif message_type == 'claim_bingo':
            result = await self.claim_player_bingo(content.get('round_number'))
            await self.send_json({'type': 'bingo_result', **result})
            if result.get('ok'):
                await self.broadcast_player_update(result['player'])
                await self.channel_layer.group_send(
                    WORLD_GROUP,
                    {
                        'type': 'bingo.winner',
                        'round_number': content['round_number'],
                        'player': result['player'],
                        'message': result['message'],
                    },
                )

    async def broadcast_player_update(self, player):
        await self.channel_layer.group_send(
            WORLD_GROUP,
            {'type': 'player.changed', 'player': player},
        )

    async def snapshot(self, event):
        await self.send_json({'type': 'snapshot', **event['data']})

    async def presence_joined(self, event):
        if event['player']['id'] != self.player_id:
            await self.send_json({'type': 'presence_joined', 'player': event['player']})

    async def presence_left(self, event):
        if event['player_id'] != self.player_id:
            await self.send_json({'type': 'presence_left', 'player_id': event['player_id']})

    async def player_moved(self, event):
        if event['player']['id'] != self.player_id:
            await self.send_json({'type': 'player_moved', 'player': event['player']})

    async def player_changed(self, event):
        await self.send_json({'type': 'player_changed', 'player': event['player']})

    async def bingo_winner(self, event):
        await self.send_json({
            'type': 'bingo_winner',
            'round_number': event['round_number'],
            'player': event['player'],
            'message': event['message'],
        })

    @database_sync_to_async
    def get_session_player(self):
        player_id = self.scope['session'].get('multiplayer_player_id')
        return MultiplayerPlayer.objects.filter(pk=player_id).first() if player_id else None

    @database_sync_to_async
    def create_presence(self):
        now = timezone.now()
        MultiplayerPresence.objects.filter(
            last_seen__lt=now - PRESENCE_TIMEOUT,
        ).delete()
        MultiplayerPresence.objects.create(
            connection_id=self.connection_id,
            player_id=self.player_id,
            avatar=self.avatar,
        )

    @database_sync_to_async
    def delete_presence(self):
        MultiplayerPresence.objects.filter(connection_id=self.connection_id).delete()

    @database_sync_to_async
    def presence_payload(self):
        presence = MultiplayerPresence.objects.select_related('player').get(
            connection_id=self.connection_id,
        )
        return {
            'id': presence.player_id,
            'name': presence.player.name,
            'donated_cans': presence.player.donated_cans,
            'x': presence.x,
            'avatar': presence.avatar,
            'custom_character': presence.player.custom_character,
        }

    @database_sync_to_async
    def latest_presence(self):
        presence = (
            MultiplayerPresence.objects
            .filter(
                player_id=self.player_id,
                last_seen__gte=timezone.now() - PRESENCE_TIMEOUT,
            )
            .select_related('player')
            .order_by('-last_seen')
            .first()
        )
        if not presence:
            return None
        return {
            'id': presence.player_id,
            'name': presence.player.name,
            'donated_cans': presence.player.donated_cans,
            'x': presence.x,
            'avatar': presence.avatar,
            'custom_character': presence.player.custom_character,
        }

    @database_sync_to_async
    def get_snapshot(self):
        return get_world_snapshot(self.player_id)

    @database_sync_to_async
    def update_player_position(self, x):
        return update_presence(self.connection_id, x, self.avatar)

    @database_sync_to_async
    def perform_player_action(self, action):
        return perform_action(self.connection_id, action)

    @database_sync_to_async
    def claim_player_bingo(self, round_number):
        if isinstance(round_number, bool) or not isinstance(round_number, int):
            return {'ok': False, 'message': 'Invalid bingo round.'}
        return claim_bingo(self.player_id, round_number)
