from django.db import models


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
