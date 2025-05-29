from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from app.consumers import InventoryConsumer  # update with your actual app and consumer

websocket_urlpatterns = [
    re_path(r'ws/inventory/$', InventoryConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
