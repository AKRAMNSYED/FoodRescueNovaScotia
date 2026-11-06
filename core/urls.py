from django.urls import path
from . import views
from . import multiplayer_views

urlpatterns = [
    path('', views.home, name='home'),
    path('chat/', views.chat, name='chat'),
    path('events/', views.events, name='events'),
    path('events/add/', views.add_event, name='add_event'),
    path('events/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('events/<int:event_id>/delete/', views.delete_event, name='delete_event'),
    path('events/<int:event_id>/register/', views.register_for_event, name='register_for_event'),
    path('events/comment/', views.add_comment, name='add_comment'),
    path('events/comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    path('game/', views.game, name='game'),
    path('game/multiplayer/', multiplayer_views.multiplayer_game, name='game_multiplayer'),
    path('game/multiplayer/auth/', multiplayer_views.multiplayer_auth, name='multiplayer_auth'),
    path('game/multiplayer/session/', multiplayer_views.multiplayer_session, name='multiplayer_session'),
    path('game/multiplayer/logout/', multiplayer_views.multiplayer_logout, name='multiplayer_logout'),
    path('game/multiplayer/leaderboard/', multiplayer_views.multiplayer_leaderboard, name='multiplayer_leaderboard'),
    path('qr-code/', views.qr_code, name='qr_code'),
    path('updates/', views.updates, name='updates'),
    path('donations/', views.donations, name='donations'),
    path('donations/create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('donations/success/', views.donation_success, name='donation_success'),
]
