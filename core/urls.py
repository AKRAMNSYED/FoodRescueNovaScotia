from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('events/', views.events, name='events'),
    path('events/add/', views.add_event, name='add_event'),
    path('events/<int:event_id>/edit/', views.edit_event, name='edit_event'),
    path('events/<int:event_id>/delete/', views.delete_event, name='delete_event'),
    path('events/<int:event_id>/register/', views.register_for_event, name='register_for_event'),
    path('events/comment/', views.add_comment, name='add_comment'),
    path('events/comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),
    path('donations/', views.donations, name='donations'),
    path('donations/create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('donations/success/', views.donation_success, name='donation_success'),
]
