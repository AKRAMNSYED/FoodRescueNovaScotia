from django.contrib import admin
from .models import Event, EventRegistration, Comment


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'location', 'seats', 'ticket_price', 'pre_registration_open', 'registration_optional', 'registration_available_to_all', 'created_at')
    search_fields = ('name', 'location')
    list_filter = ('date', 'pre_registration_open', 'registration_optional', 'registration_available_to_all')


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('event', 'name', 'email', 'quantity', 'created_at')
    search_fields = ('name', 'email', 'event__name')


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('name', 'message', 'created_at')
    search_fields = ('name', 'message')
    list_filter = ('created_at',)
