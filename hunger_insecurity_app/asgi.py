"""
ASGI config for hunger_insecurity_app project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.sessions import SessionMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hunger_insecurity_app.settings')

django_application = get_asgi_application()

from core.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_application,
    'websocket': AllowedHostsOriginValidator(
        SessionMiddlewareStack(URLRouter(websocket_urlpatterns))
    ),
})
