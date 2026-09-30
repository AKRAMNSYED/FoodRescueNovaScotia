from django.contrib import admin, messages
from django.core.exceptions import ObjectDoesNotExist
from .models import ChangeProposal, Event, EventRegistration, Comment

admin.site.index_template = 'core/admin/index.html'


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'location', 'seats', 'ticket_price', 'pre_registration_open', 'registration_optional', 'registration_available_to_all', 'created_at')
    search_fields = ('name', 'location')
    list_filter = ('date', 'pre_registration_open', 'registration_optional', 'registration_available_to_all')

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ('event', 'name', 'email', 'quantity', 'created_at')
    search_fields = ('name', 'email', 'event__name')

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('name', 'message', 'created_at')
    search_fields = ('name', 'message')
    list_filter = ('created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ChangeProposal)
class ChangeProposalAdmin(admin.ModelAdmin):
    list_display = ('action', 'status', 'proposed_by', 'created_at', 'reviewed_by', 'reviewed_at')
    list_filter = ('status', 'action', 'created_at')
    search_fields = ('proposed_by__username', 'payload')
    readonly_fields = (
        'action', 'status', 'target_id', 'payload', 'proposed_by', 'reviewed_by',
        'created_at', 'reviewed_at',
    )
    actions = ('approve_selected', 'reject_selected')

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description='Approve selected proposals')
    def approve_selected(self, request, queryset):
        approved = 0
        for proposal in queryset.filter(status=ChangeProposal.Status.PENDING):
            try:
                approved += proposal.approve(request.user)
            except ObjectDoesNotExist:
                self.message_user(
                    request,
                    f'Proposal {proposal.pk} could not be applied because its target no longer exists.',
                    level=messages.ERROR,
                )
        if approved:
            self.message_user(request, f'{approved} proposal(s) approved.', level=messages.SUCCESS)

    @admin.action(description='Reject selected proposals')
    def reject_selected(self, request, queryset):
        rejected = 0
        for proposal in queryset.filter(status=ChangeProposal.Status.PENDING):
            rejected += proposal.reject(request.user)
        if rejected:
            self.message_user(request, f'{rejected} proposal(s) rejected.', level=messages.SUCCESS)
