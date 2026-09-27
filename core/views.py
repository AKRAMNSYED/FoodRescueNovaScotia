import stripe
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from .models import Event, EventRegistration, Comment

stripe.api_key = settings.STRIPE_SECRET_KEY


def home(request):
    return render(request, 'core/home.html')


def events(request):
    event_list = Event.objects.all().order_by('-date')
    comment_list = Comment.objects.all().order_by('-created_at')
    return render(request, 'core/events.html', {
        'events': event_list,
        'comments': comment_list,
    })


def add_event(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        date = request.POST.get('date', '').strip()
        location = request.POST.get('location', '').strip()
        description = request.POST.get('description', '').strip()
        seats = request.POST.get('seats', '0').strip()
        ticket_price = request.POST.get('ticket_price', '0').strip()
        pre_registration_open = request.POST.get('pre_registration_open') == 'on'
        registration_optional = request.POST.get('registration_optional') == 'on'
        registration_available_to_all = request.POST.get('registration_available_to_all') == 'on'

        try:
            seats = int(seats)
        except ValueError:
            seats = 0

        try:
            ticket_price = float(ticket_price)
        except ValueError:
            ticket_price = 0.0

        if name and date and location:
            Event.objects.create(
                name=name,
                date=date,
                location=location,
                description=description,
                seats=seats,
                ticket_price=ticket_price,
                pre_registration_open=pre_registration_open,
                registration_optional=registration_optional,
                registration_available_to_all=registration_available_to_all,
            )
    return redirect('events')


@staff_member_required
def edit_event(request, event_id):
    event = Event.objects.filter(id=event_id).first()
    if not event:
        return redirect('events')

    if request.method == 'POST':
        event.name = request.POST.get('name', event.name).strip()
        event.date = request.POST.get('date', event.date)
        event.location = request.POST.get('location', event.location).strip()
        event.description = request.POST.get('description', event.description).strip()

        try:
            event.seats = int(request.POST.get('seats', event.seats))
        except ValueError:
            event.seats = 0

        try:
            event.ticket_price = float(request.POST.get('ticket_price', event.ticket_price))
        except ValueError:
            event.ticket_price = 0.0

        event.pre_registration_open = request.POST.get('pre_registration_open') == 'on'
        event.registration_optional = request.POST.get('registration_optional') == 'on'
        event.registration_available_to_all = request.POST.get('registration_available_to_all') == 'on'

        if event.name and event.date and event.location:
            event.save()
        return redirect('events')

    return render(request, 'core/edit_event.html', {'event': event})


@staff_member_required
def delete_event(request, event_id):
    event = Event.objects.filter(id=event_id).first()
    if event:
        event.delete()
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
def delete_comment(request, comment_id):
    comment = Comment.objects.filter(id=comment_id).first()
    if comment:
        comment.delete()
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
