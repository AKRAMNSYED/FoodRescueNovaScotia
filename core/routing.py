from django.urls import path

from .consumers import MultiplayerConsumer

websocket_urlpatterns = [
    path('ws/game/multiplayer/', MultiplayerConsumer.as_asgi()),
]
