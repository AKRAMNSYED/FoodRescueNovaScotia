import json
import re

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import MultiplayerPlayer
from .multiplayer import clean_player_name, game_timing

DEFAULT_CUSTOM_CHARACTER = {
    'hair': 'long',
    'hairColor': '#ffeb3b',
    'skin': '#ffecb3',
    'shirt': '#8bc34a',
    'pants': '#0288d1',
    'shoes': '#f44336',
    'shoulders': 0,
    'hat': False,
    'hatColor': '#689f38',
}
CUSTOM_CHARACTER_COLORS = (
    'hairColor',
    'skin',
    'shirt',
    'pants',
    'shoes',
    'hatColor',
)


def _custom_character_config(value):
    if not isinstance(value, dict):
        return None
    config = DEFAULT_CUSTOM_CHARACTER.copy()
    for key in CUSTOM_CHARACTER_COLORS:
        color = value.get(key, config[key])
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            return None
        config[key] = color.lower()
    hair = value.get('hair', config['hair'])
    shoulders = value.get('shoulders', config['shoulders'])
    hat = value.get('hat', config['hat'])
    if hair not in {'long', 'short'}:
        return None
    if isinstance(shoulders, bool) or shoulders not in {0, 1, 2}:
        return None
    if not isinstance(hat, bool):
        return None
    config.update({'hair': hair, 'shoulders': shoulders, 'hat': hat})
    return config


@ensure_csrf_cookie
def multiplayer_game(request):
    return render(request, 'core/multiplayer.html', {
        'multiplayer_available': settings.MULTIPLAYER_AVAILABLE,
    })


def _json_body(request):
    try:
        body = json.loads(request.body or b'{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _unavailable_response():
    return JsonResponse({
        'error': (
            'Multiplayer is not configured on this server yet. '
            'Connect Railway Redis and a persistent database, then redeploy.'
        ),
    }, status=503)


@require_POST
def multiplayer_auth(request):
    if not settings.MULTIPLAYER_AVAILABLE:
        return _unavailable_response()
    payload = _json_body(request)
    if payload is None:
        return JsonResponse({'error': 'Invalid request data.'}, status=400)

    mode = payload.get('mode')
    name = payload.get('name', '')
    password = payload.get('password', '')
    avatar = payload.get('avatar', 'eve')
    custom_character = _custom_character_config(payload.get('custom_character', {}))
    if not isinstance(name, str) or not isinstance(password, str):
        return JsonResponse({'error': 'Enter a player name and password.'}, status=400)
    if avatar not in {'eve', 'jim', 'custom'}:
        avatar = 'eve'
    if custom_character is None:
        return JsonResponse({'error': 'The custom character options are invalid.'}, status=400)
    cleaned_name = clean_player_name(name)
    if not cleaned_name:
        return JsonResponse({
            'error': 'Choose a 2–16 character, family-friendly player name.',
        }, status=400)
    normalized_name = cleaned_name.casefold()

    if mode == 'register':
        if not 8 <= len(password) <= 128:
            return JsonResponse({
                'error': 'Your password must be between 8 and 128 characters.',
            }, status=400)
        timing = game_timing()
        try:
            player = MultiplayerPlayer.objects.create(
                name=cleaned_name,
                normalized_name=normalized_name,
                password_hash=make_password(password),
                avatar=avatar,
                custom_character=custom_character,
                balance=15,
                last_paid_day=timing['cycle_number'],
            )
        except IntegrityError:
            return JsonResponse({'error': 'That player name is already in use.'}, status=409)
    elif mode == 'login':
        player = MultiplayerPlayer.objects.filter(
            normalized_name=normalized_name,
        ).first()
        if player is None or not check_password(password, player.password_hash):
            return JsonResponse({'error': 'That name and password do not match.'}, status=401)
    else:
        return JsonResponse({'error': 'Choose register or login.'}, status=400)

    request.session.cycle_key()
    request.session['multiplayer_player_id'] = player.pk
    return JsonResponse({
        'player': {
            'id': player.pk,
            'name': player.name,
            'balance': player.balance,
            'cans_held': player.cans_held,
            'donated_cans': player.donated_cans,
            'soccer_balls': player.soccer_balls,
            'avatar': player.avatar,
            'custom_character': player.custom_character,
        },
    })


@require_GET
def multiplayer_session(request):
    if not settings.MULTIPLAYER_AVAILABLE:
        return _unavailable_response()
    player_id = request.session.get('multiplayer_player_id')
    player = MultiplayerPlayer.objects.filter(pk=player_id).first() if player_id else None
    if not player:
        return JsonResponse({'authenticated': False, 'player': None})
    return JsonResponse({
        'authenticated': True,
        'player': {
            'id': player.pk,
            'name': player.name,
            'balance': player.balance,
            'cans_held': player.cans_held,
            'donated_cans': player.donated_cans,
            'soccer_balls': player.soccer_balls,
            'avatar': player.avatar,
            'custom_character': player.custom_character,
        },
    })


@require_POST
def multiplayer_logout(request):
    request.session.pop('multiplayer_player_id', None)
    request.session.cycle_key()
    return JsonResponse({'ok': True})


@require_GET
def multiplayer_leaderboard(request):
    if not settings.MULTIPLAYER_AVAILABLE:
        return _unavailable_response()
    players = MultiplayerPlayer.objects.order_by('-donated_cans', 'name')[:100]
    return JsonResponse({
        'players': [
            {'rank': index, 'name': player.name, 'donated_cans': player.donated_cans}
            for index, player in enumerate(players, start=1)
        ],
    })
