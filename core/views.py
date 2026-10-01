import stripe
from decimal import Decimal, InvalidOperation
from django import forms
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from .models import ChangeProposal, Event, EventRegistration, Comment, StaffChatMessage

stripe.api_key = settings.STRIPE_SECRET_KEY


def home(request):
    return render(request, 'core/home.html')


def _display_name_for_user(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return 'Guest'

    if user.get_full_name():
        return user.get_full_name()

    username = user.username.strip()
    if username.lower() in {'admin', 'msmathesonil'}:
        return 'Ms Matheson'
    return username


def events(request):
    event_list = Event.objects.all().order_by('-date')
    comment_list = Comment.objects.all().order_by('-created_at')
    pending_proposals = ChangeProposal.objects.filter(
        proposed_by=request.user,
        status=ChangeProposal.Status.PENDING,
    ).count() if request.user.is_authenticated else 0
    return render(request, 'core/events.html', {
        'events': event_list,
        'comments': comment_list,
        'pending_proposals': pending_proposals,
    })


@staff_member_required
def chat(request):
    chat_messages = StaffChatMessage.objects.select_related('sender').all().order_by('created_at')

    if request.method == 'POST':
        message = request.POST.get('message', '').strip()
        if message:
            StaffChatMessage.objects.create(sender=request.user, message=message)
        return redirect('chat')

    return render(request, 'core/chat.html', {
        'chat_messages': chat_messages,
        'display_name': _display_name_for_user(request.user),
    })


def _event_payload(request, event=None):
    name = request.POST.get('name', event.name if event else '').strip()
    location = request.POST.get('location', event.location if event else '').strip()
    description = request.POST.get('description', event.description if event else '').strip()
    try:
        event_date = forms.DateField().clean(request.POST.get('date', event.date if event else ''))
        seats = int(request.POST.get('seats', event.seats if event else '0'))
        ticket_price = Decimal(request.POST.get('ticket_price', event.ticket_price if event else '0'))
    except (forms.ValidationError, ValueError, InvalidOperation):
        return None

    if not name or not location or seats < 0 or ticket_price < 0:
        return None

    return {
        'name': name,
            'date': event_date.isoformat(),
        'location': location,
        'description': description,
        'seats': seats,
        'ticket_price': str(ticket_price),
        'pre_registration_open': request.POST.get('pre_registration_open') == 'on',
        'registration_optional': request.POST.get('registration_optional') == 'on',
        'registration_available_to_all': request.POST.get('registration_available_to_all') == 'on',
    }


@staff_member_required
@require_POST
def add_event(request):
    payload = _event_payload(request)
    if payload is None:
        messages.error(request, 'Please enter valid event details.')
        return redirect('events')

    if request.user.is_superuser:
        Event.objects.create(**payload)
        messages.success(request, 'Event published.')
    else:
        ChangeProposal.objects.create(
            action=ChangeProposal.Action.CREATE_EVENT,
            payload=payload,
            proposed_by=request.user,
        )
        messages.success(request, 'Event submitted for main admin approval.')
    return redirect('events')


@staff_member_required
def edit_event(request, event_id):
    event = Event.objects.filter(id=event_id).first()
    if not event:
        return redirect('events')

    if request.method == 'POST':
        payload = _event_payload(request, event)
        if payload is None:
            messages.error(request, 'Please enter valid event details.')
            return redirect('edit_event', event_id=event.id)

        if request.user.is_superuser:
            for field, value in payload.items():
                setattr(event, field, value)
            event.save()
            messages.success(request, 'Event updated.')
        else:
            ChangeProposal.objects.create(
                action=ChangeProposal.Action.UPDATE_EVENT,
                target_id=event.id,
                payload=payload,
                proposed_by=request.user,
            )
            messages.success(request, 'Event update submitted for main admin approval.')
        return redirect('events')

    return render(request, 'core/edit_event.html', {'event': event})


@staff_member_required
@require_POST
def delete_event(request, event_id):
    event = Event.objects.filter(id=event_id).first()
    if event:
        if request.user.is_superuser:
            event.delete()
            messages.success(request, 'Event deleted.')
        else:
            ChangeProposal.objects.create(
                action=ChangeProposal.Action.DELETE_EVENT,
                target_id=event.id,
                payload={'name': event.name},
                proposed_by=request.user,
            )
            messages.success(request, 'Event deletion submitted for main admin approval.')
    return redirect('events')


def register_for_event(request, event_id):
    event = Event.objects.filter(id=event_id).first()
    if not event:
        return redirect('events')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        quantity = request.POST.get('quantity', '1').strip()

        try:
            quantity = int(quantity)
        except ValueError:
            quantity = 1

        if quantity < 1:
            quantity = 1

        if event.seats and event.seats_left != 'Unlimited':
            used = sum(reg.quantity for reg in event.registrations.all())
            if used + quantity > event.seats:
                return redirect('events')

        if name and email:
            EventRegistration.objects.create(
                event=event,
                name=name,
                email=email,
                quantity=quantity,
            )

    return redirect('events')


def add_comment(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        message = request.POST.get('message', '').strip()

        if name and message:
            Comment.objects.create(name=name, message=message)
    return redirect('events')


@staff_member_required
@require_POST
def delete_comment(request, comment_id):
    comment = Comment.objects.filter(id=comment_id).first()
    if comment:
        if request.user.is_superuser:
            comment.delete()
            messages.success(request, 'Comment deleted.')
        else:
            ChangeProposal.objects.create(
                action=ChangeProposal.Action.DELETE_COMMENT,
                target_id=comment.id,
                payload={'name': comment.name, 'message': comment.message},
                proposed_by=request.user,
            )
            messages.success(request, 'Comment removal submitted for main admin approval.')
    return redirect('events')


def donations(request):
    return render(request, 'core/donations.html', {
        'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY,
    })


def create_checkout_session(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    try:
        amount = int(request.POST.get('amount', '0'))
    except ValueError:
        return JsonResponse({'error': 'Please enter a valid donation amount.'}, status=400)

    if amount <= 0:
        return JsonResponse({'error': 'Donation amount must be greater than zero.'}, status=400)

    if not settings.STRIPE_SECRET_KEY:
        return JsonResponse({'checkout_url': 'http://127.0.0.1:8000/donations/success/?demo=1'})

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'cad',
                    'product_data': {
                        'name': 'Nova Scotia Hunger Insecurity Donation',
                    },
                    'unit_amount': amount * 100,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='http://127.0.0.1:8000/donations/success/',
            cancel_url='http://127.0.0.1:8000/donations/',
        )
    except Exception as exc:
        return JsonResponse({'error': str(exc)}, status=400)

    return JsonResponse({'checkout_url': session.url})


def donation_success(request):
    demo_mode = request.GET.get('demo') == '1'
    return render(request, 'core/donation_success.html', {'demo_mode': demo_mode})
