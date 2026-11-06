import hashlib
import math
import random
import re
import unicodedata
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import (
    MultiplayerBingoWinner,
    MultiplayerGameClock,
    MultiplayerPlayer,
    MultiplayerPresence,
)

DAY_SECONDS = 300
NIGHT_SECONDS = 300
ROUND_SECONDS = 100
CAN_PRICE = 5
DAY_PAY = 15
STORE_X = 450
FEED_X = -450
ACTION_RADIUS = 105
PRESENCE_TIMEOUT = timedelta(seconds=20)

_LEET = str.maketrans({
    '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '8': 'b',
    '@': 'a', '$': 's', '!': 'i', '+': 't',
})
_BLOCKED_COMPACT = (
    'fuck', 'shit', 'bitch', 'nigg', 'faggot', 'whore', 'slut',
    'pussy', 'penis', 'vagina', 'rapist', 'hitler', 'retard', 'bastard',
    'asshole', 'twat', 'wank', 'porn', 'molest', 'tranny', 'chink', 'spic',
    'kike',
)
_BLOCKED_WHOLE = {
    'ass', 'arse', 'damn', 'hell', 'piss', 'crap', 'sex', 'tit', 'tits',
    'boob', 'boobs', 'fag', 'gay', 'cum', 'anal', 'nude', 'dick', 'dicks',
    'cock', 'cocks', 'cunt', 'rape', 'nazi', 'pedo', 'dyke', 'paki',
}


def clean_player_name(value):
    name = ' '.join(unicodedata.normalize('NFKC', value).strip().split())
    if not 2 <= len(name) <= 16 or not re.fullmatch(r"[\w .'-]+", name):
        return None

    decoded = name.casefold().translate(_LEET)
    words = re.findall(r'[a-z]+', decoded)
    collapsed = [re.sub(r'(.)\1+', r'\1', word) for word in words]
    compact = re.sub(r'[^a-z]', '', decoded)
    compact = re.sub(r'(.)\1+', r'\1', compact)
    if (
        any(term in compact for term in _BLOCKED_COMPACT)
        or any(word in _BLOCKED_WHOLE for word in words + collapsed)
    ):
        return None
    return name


def _game_clock():
    try:
        return MultiplayerGameClock.objects.get(pk=1)
    except MultiplayerGameClock.DoesNotExist:
        try:
            return MultiplayerGameClock.objects.create(pk=1)
        except IntegrityError:
            return MultiplayerGameClock.objects.get(pk=1)


def _round_seed(clock, cycle_number, round_number):
    value = f'{clock.started_at.isoformat()}:{cycle_number}:{round_number}'
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], 'big')


def bingo_calls(clock, cycle_number, round_number):
    return random.Random(_round_seed(clock, cycle_number, round_number)).sample(
        range(1, 76),
        75,
    )


def bingo_card(player_id, clock, cycle_number, round_number):
    rng = random.Random(
        _round_seed(clock, cycle_number, round_number) ^ (player_id * 7919)
    )
    columns = [
        rng.sample(range(start, start + 15), 5)
        for start in (1, 16, 31, 46, 61)
    ]
    return [
        ['FREE' if row == 2 and column == 2 else columns[column][row]
         for column in range(5)]
        for row in range(5)
    ]


def game_timing(now=None):
    now = now or timezone.now()
    clock = _game_clock()
    seconds = max(0, (now - clock.started_at).total_seconds())
    cycle_number = int(seconds // (DAY_SECONDS + NIGHT_SECONDS))
    cycle_seconds = seconds % (DAY_SECONDS + NIGHT_SECONDS)
    if cycle_seconds < DAY_SECONDS:
        phase = 'day'
        phase_seconds = cycle_seconds
        round_number = None
        round_seconds = 0
    else:
        phase = 'night'
        night_seconds = cycle_seconds - DAY_SECONDS
        phase_seconds = night_seconds
        round_number = min(3, int(night_seconds // ROUND_SECONDS) + 1)
        round_seconds = night_seconds % ROUND_SECONDS

    timing = {
        'clock': clock,
        'cycle_number': cycle_number,
        'phase': phase,
        'phase_seconds_left': max(
            0,
            math.ceil((DAY_SECONDS if phase == 'day' else NIGHT_SECONDS) - phase_seconds),
        ),
        'round_number': round_number,
        'round_seconds_left': max(0, math.ceil(ROUND_SECONDS - round_seconds)),
        'called_count': min(75, max(0, int(round_seconds))) if phase == 'night' else 0,
    }
    return timing


def _player_payload(player):
    return {
        'id': player.pk,
        'name': player.name,
        'avatar': player.avatar,
        'balance': player.balance,
        'cans_held': player.cans_held,
        'donated_cans': player.donated_cans,
        'soccer_balls': player.soccer_balls,
    }


def get_world_snapshot(player_id, now=None):
    now = now or timezone.now()
    timing = game_timing(now)
    with transaction.atomic():
        player = MultiplayerPlayer.objects.select_for_update().get(pk=player_id)
        if timing['phase'] == 'day' and player.last_paid_day < timing['cycle_number']:
            player.balance += DAY_PAY
            player.last_paid_day = timing['cycle_number']
            player.save(update_fields=('balance', 'last_paid_day'))

    presence_qs = (
        MultiplayerPresence.objects
        .filter(last_seen__gte=now - PRESENCE_TIMEOUT)
        .select_related('player')
        .order_by('-last_seen')
    )
    active_players = []
    seen = set()
    for presence in presence_qs:
        if presence.player_id in seen:
            continue
        seen.add(presence.player_id)
        active_players.append({
            'id': presence.player_id,
            'name': presence.player.name,
            'donated_cans': presence.player.donated_cans,
            'x': presence.x,
            'avatar': presence.avatar,
        })

    round_no = timing['round_number']
    if timing['phase'] == 'night' and round_no:
        calls = bingo_calls(timing['clock'], timing['cycle_number'], round_no)
        winners = list(
            MultiplayerBingoWinner.objects
            .filter(cycle_number=timing['cycle_number'], round_number=round_no)
            .select_related('player')
            .order_by('created_at')[:3]
        )
        bingo = {
            'round_number': round_no,
            'round_seconds_left': timing['round_seconds_left'],
            'calls': calls[:timing['called_count']],
            'card': bingo_card(player_id, timing['clock'], timing['cycle_number'], round_no),
            'winners': [
                {'id': winner.player_id, 'name': winner.player.name}
                for winner in winners
            ],
        }
    else:
        bingo = None

    return {
        'player': _player_payload(MultiplayerPlayer.objects.get(pk=player_id)),
        'online_players': active_players,
        'phase': timing['phase'],
        'phase_seconds_left': timing['phase_seconds_left'],
        'cycle_number': timing['cycle_number'],
        'round_number': round_no,
        'bingo': bingo,
    }


def update_presence(connection_id, x, avatar, now=None):
    now = now or timezone.now()
    if (
        avatar not in {'eve', 'jim'}
        or isinstance(x, bool)
        or not isinstance(x, (int, float))
        or not math.isfinite(x)
    ):
        return None
    presence = MultiplayerPresence.objects.filter(connection_id=connection_id).first()
    if presence is None:
        return None
    x = max(-2500.0, min(2500.0, float(x)))
    elapsed = max(0.05, (now - presence.last_seen).total_seconds())
    if abs(x - presence.x) > max(45, elapsed * 400):
        return None
    MultiplayerPresence.objects.filter(connection_id=connection_id).update(
        x=x,
        avatar=avatar,
        last_seen=now,
    )
    presence.x = x
    presence.avatar = avatar
    presence.last_seen = now
    return {
        'id': presence.player_id,
        'name': presence.player.name,
        'donated_cans': presence.player.donated_cans,
        'x': x,
        'avatar': avatar,
    }


def perform_action(connection_id, action, now=None):
    now = now or timezone.now()
    timing = game_timing(now)
    if timing['phase'] != 'day':
        return {'ok': False, 'message': 'Stores and donations are available during daytime.'}

    with transaction.atomic():
        presence = (
            MultiplayerPresence.objects
            .select_for_update()
            .select_related('player')
            .filter(connection_id=connection_id)
            .first()
        )
        if presence is None:
            return {'ok': False, 'message': 'Your game connection has expired.'}
        player = MultiplayerPlayer.objects.select_for_update().get(pk=presence.player_id)
        if action == 'buy':
            if abs(presence.x - STORE_X) > ACTION_RADIUS:
                return {'ok': False, 'message': 'Go to Sobeys to buy a can.'}
            if player.balance < CAN_PRICE:
                return {'ok': False, 'message': 'You need $5 to buy a can.'}
            player.balance -= CAN_PRICE
            player.cans_held += 1
            message = 'You bought a can for $5.'
        elif action == 'donate':
            if abs(presence.x - FEED_X) > ACTION_RADIUS:
                return {'ok': False, 'message': 'Go to Feed Nova Scotia to donate a can.'}
            if player.cans_held < 1:
                return {'ok': False, 'message': 'Buy a can at Sobeys before donating.'}
            player.cans_held -= 1
            player.donated_cans += 1
            message = 'Thank you for donating a can to Feed Nova Scotia!'
        else:
            return {'ok': False, 'message': 'That game action is not available.'}
        player.save(update_fields=('balance', 'cans_held', 'donated_cans'))

    return {'ok': True, 'message': message, 'player': _player_payload(player)}


def claim_bingo(player_id, round_number, now=None):
    now = now or timezone.now()
    timing = game_timing(now)
    if timing['phase'] != 'night' or timing['round_number'] != round_number:
        return {'ok': False, 'message': 'That bingo round is no longer active.'}

    calls = bingo_calls(timing['clock'], timing['cycle_number'], round_number)
    called = set(calls[:timing['called_count']])
    card = bingo_card(player_id, timing['clock'], timing['cycle_number'], round_number)
    diagonal = [card[index][index] for index in range(5) if index != 2]
    if not all(number in called for number in diagonal):
        return {'ok': False, 'message': 'Your diagonal is not complete yet.'}

    with transaction.atomic():
        MultiplayerGameClock.objects.select_for_update().get(pk=1)
        player = MultiplayerPlayer.objects.select_for_update().get(pk=player_id)
        winners = MultiplayerBingoWinner.objects.filter(
            cycle_number=timing['cycle_number'],
            round_number=round_number,
        )
        if winners.filter(player=player).exists():
            return {'ok': True, 'message': 'You already won this round.'}
        if winners.count() >= 3:
            return {'ok': False, 'message': 'All three winner spots are taken.'}
        try:
            slot = winners.count() + 1
            MultiplayerBingoWinner.objects.create(
                cycle_number=timing['cycle_number'],
                round_number=round_number,
                winner_slot=slot,
                player=player,
            )
        except IntegrityError:
            return {'ok': False, 'message': 'You already claimed this round.'}
        player.soccer_balls += 1
        player.save(update_fields=('soccer_balls',))

    return {'ok': True, 'message': 'Bingo! You won a soccer ball.', 'player': _player_payload(player)}
