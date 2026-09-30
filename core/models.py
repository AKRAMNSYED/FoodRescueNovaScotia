from django.db import models
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from datetime import date
from decimal import Decimal


class Event(models.Model):
    name = models.CharField(max_length=200)
    date = models.DateField()
    location = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    seats = models.PositiveIntegerField(default=0, help_text='Set 0 for unlimited seats.')
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pre_registration_open = models.BooleanField(default=False)
    registration_optional = models.BooleanField(default=True, help_text='If enabled, registration is optional for attendees.')
    registration_available_to_all = models.BooleanField(default=True, help_text='If enabled, the registration form is available to everyone.')
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def seats_left(self):
        if self.seats == 0:
            return 'Unlimited'
        used = sum(registration.quantity for registration in self.registrations.all())
        return max(self.seats - used, 0)

    def __str__(self):
        return self.name


class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    name = models.CharField(max_length=100)
    email = models.EmailField()
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.event.name}"


class Comment(models.Model):
    name = models.CharField(max_length=100)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name}: {self.message[:40]}"


class ChangeProposal(models.Model):
    class Action(models.TextChoices):
        CREATE_EVENT = 'create_event', 'Create event'
        UPDATE_EVENT = 'update_event', 'Update event'
        DELETE_EVENT = 'delete_event', 'Delete event'
        DELETE_COMMENT = 'delete_comment', 'Delete comment'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    action = models.CharField(max_length=20, choices=Action.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    proposed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='change_proposals',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_change_proposals',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'change proposal'
        verbose_name_plural = 'change proposals'

    def __str__(self):
        return f'{self.get_action_display()} ({self.get_status_display()})'

    def approve(self, reviewer):
        if not reviewer.is_superuser:
            raise PermissionDenied('Only a superuser can approve changes.')

        with transaction.atomic():
            proposal = ChangeProposal.objects.select_for_update().get(pk=self.pk)
            if proposal.status != self.Status.PENDING:
                return False

            if proposal.action == self.Action.CREATE_EVENT:
                payload = proposal.payload.copy()
                payload['date'] = date.fromisoformat(payload['date'])
                payload['ticket_price'] = Decimal(payload['ticket_price'])
                Event.objects.create(**payload)
            elif proposal.action == self.Action.UPDATE_EVENT:
                event = Event.objects.select_for_update().get(pk=proposal.target_id)
                payload = proposal.payload.copy()
                payload['date'] = date.fromisoformat(payload['date'])
                payload['ticket_price'] = Decimal(payload['ticket_price'])
                for field, value in payload.items():
                    setattr(event, field, value)
                event.save()
            elif proposal.action == self.Action.DELETE_EVENT:
                Event.objects.filter(pk=proposal.target_id).delete()
            elif proposal.action == self.Action.DELETE_COMMENT:
                Comment.objects.filter(pk=proposal.target_id).delete()

            proposal.status = self.Status.APPROVED
            proposal.reviewed_by = reviewer
            proposal.reviewed_at = timezone.now()
            proposal.save(update_fields=('status', 'reviewed_by', 'reviewed_at'))
            return True

    def reject(self, reviewer):
        if not reviewer.is_superuser:
            raise PermissionDenied('Only a superuser can reject changes.')

        if self.status != self.Status.PENDING:
            return False
        self.status = self.Status.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save(update_fields=('status', 'reviewed_by', 'reviewed_at'))
        return True
