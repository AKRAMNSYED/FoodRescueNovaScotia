from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.management.base import CommandError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
	ChangeProposal,
	Comment,
	Event,
	MultiplayerBingoWinner,
	MultiplayerGameClock,
	MultiplayerPlayer,
	MultiplayerPresence,
)
from .multiplayer import (
	DAY_PAY,
	claim_bingo,
	clean_player_name,
	game_timing,
	get_world_snapshot,
	perform_action,
)
from .multiplayer_views import DEFAULT_CUSTOM_CHARACTER, _custom_character_config


class SubadminApprovalTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.subadmin = user_model.objects.create_user(
			username='subadmin',
			password='test-password',
			is_staff=True,
		)
		self.main_admin = user_model.objects.create_superuser(
			username='mainadmin',
			password='test-password',
			email='mainadmin@example.com',
		)
		self.event = Event.objects.create(
			name='Community supper',
			date=date(2027, 5, 10),
			location='Halifax',
		)

	def event_form_data(self, name='Community supper'):
		return {
			'name': name,
			'date': '2027-05-10',
			'location': 'Halifax',
			'description': 'Open community meal',
			'seats': '40',
			'ticket_price': '5.00',
			'pre_registration_open': 'on',
			'registration_optional': 'on',
			'registration_available_to_all': 'on',
		}

	def approve_through_admin(self, proposal):
		self.client.force_login(self.main_admin)
		return self.client.post(
			reverse('admin:core_changeproposal_changelist'),
			{
				'action': 'approve_selected',
				'_selected_action': [proposal.pk],
				'index': 0,
			},
		)

	def test_subadmin_event_creation_requires_main_admin_approval(self):
		self.client.force_login(self.subadmin)
		response = self.client.post(reverse('add_event'), self.event_form_data('Spring lunch'))

		self.assertRedirects(response, reverse('events'))
		self.assertFalse(Event.objects.filter(name='Spring lunch').exists())
		proposal = ChangeProposal.objects.get(action=ChangeProposal.Action.CREATE_EVENT)
		self.assertEqual(proposal.status, ChangeProposal.Status.PENDING)

		self.approve_through_admin(proposal)

		self.assertTrue(Event.objects.filter(name='Spring lunch').exists())
		proposal.refresh_from_db()
		self.assertEqual(proposal.status, ChangeProposal.Status.APPROVED)
		self.assertEqual(proposal.reviewed_by, self.main_admin)

	def test_subadmin_event_edit_stays_pending_until_approved(self):
		self.client.force_login(self.subadmin)
		self.client.post(
			reverse('edit_event', args=[self.event.pk]),
			self.event_form_data('Updated supper'),
		)

		self.event.refresh_from_db()
		self.assertEqual(self.event.name, 'Community supper')
		proposal = ChangeProposal.objects.get(action=ChangeProposal.Action.UPDATE_EVENT)
		self.approve_through_admin(proposal)

		self.event.refresh_from_db()
		self.assertEqual(self.event.name, 'Updated supper')

	def test_subadmin_event_deletion_stays_pending_until_approved(self):
		self.client.force_login(self.subadmin)
		self.client.post(reverse('delete_event', args=[self.event.pk]))

		self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())
		proposal = ChangeProposal.objects.get(action=ChangeProposal.Action.DELETE_EVENT)
		self.approve_through_admin(proposal)

		self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

	def test_subadmin_comment_removal_stays_pending_until_approved(self):
		comment = Comment.objects.create(name='Visitor', message='A public comment')
		self.client.force_login(self.subadmin)
		self.client.post(reverse('delete_comment', args=[comment.pk]))

		self.assertTrue(Comment.objects.filter(pk=comment.pk).exists())
		proposal = ChangeProposal.objects.get(action=ChangeProposal.Action.DELETE_COMMENT)
		self.approve_through_admin(proposal)

		self.assertFalse(Comment.objects.filter(pk=comment.pk).exists())

	def test_subadmin_cannot_edit_events_directly_in_django_admin(self):
		self.client.force_login(self.subadmin)

		response = self.client.get(reverse('admin:core_event_change', args=[self.event.pk]))

		self.assertEqual(response.status_code, 403)

	def test_nonstaff_user_cannot_submit_event_changes(self):
		user = get_user_model().objects.create_user(username='visitor', password='test-password')
		self.client.force_login(user)

		response = self.client.post(reverse('add_event'), self.event_form_data('Unapproved event'))

		self.assertEqual(response.status_code, 302)
		self.assertFalse(Event.objects.filter(name='Unapproved event').exists())
		self.assertFalse(ChangeProposal.objects.exists())

	def test_staff_chat_page_is_visible_to_staff_and_uses_display_name(self):
		self.subadmin.username = 'MsMathesonIl'
		self.subadmin.save(update_fields=['username'])
		self.client.force_login(self.subadmin)

		response = self.client.get(reverse('chat'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Ms Matheson')

	def test_nonstaff_user_cannot_access_chat_page(self):
		user = get_user_model().objects.create_user(username='visitor', password='test-password')
		self.client.force_login(user)

		response = self.client.get(reverse('chat'))

		self.assertNotEqual(response.status_code, 200)

	def test_admin_chat_shows_akram_syed_and_handles_profile_image(self):
		self.main_admin.first_name = 'Akram'
		self.main_admin.last_name = 'Syed'
		self.main_admin.save(update_fields=['first_name', 'last_name'])
		self.client.force_login(self.main_admin)

		response = self.client.get(reverse('chat'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Akram Syed')
		self.assertNotContains(response, 'Ms Matheson')
		self.assertIsNone(response.context['profile_image_url'])


class CreateSubadminsCommandTests(TestCase):
	@patch(
		'builtins.input',
		side_effect=['A-long-random-test-passphrase-73!', 'A-long-random-test-passphrase-73!'],
	)
	def test_creates_staff_only_account_and_sets_hashed_password(self, mocked_getpass):
		output = StringIO()

		call_command('create_subadmins', 'event-helper', stdout=output)

		user = get_user_model().objects.get(username='event-helper')
		self.assertTrue(user.is_active)
		self.assertTrue(user.is_staff)
		self.assertFalse(user.is_superuser)
		self.assertTrue(user.check_password('A-long-random-test-passphrase-73!'))
		self.assertNotIn('A-long-random-test-passphrase-73!', output.getvalue())
		self.assertEqual(mocked_getpass.call_count, 2)

	@patch('builtins.input', side_effect=['EmeryBoswell1!', 'EmeryBoswell1!'])
	def test_allows_passwords_similar_to_username_for_subadmins(self, mocked_getpass):
		output = StringIO()

		call_command('create_subadmins', 'EmeryBoswell', stdout=output)

		user = get_user_model().objects.get(username='EmeryBoswell')
		self.assertTrue(user.is_staff)
		self.assertFalse(user.is_superuser)
		self.assertTrue(user.check_password('EmeryBoswell1!'))
		self.assertEqual(mocked_getpass.call_count, 2)

	@patch('builtins.input', side_effect=['A-long-random-test-passphrase-73!'] * 34)
	def test_no_arguments_provisions_the_default_username_roster(self, mocked_input):
		from core.management.commands.create_subadmins import DEFAULT_SUBADMIN_USERNAMES

		output = StringIO()
		call_command('create_subadmins', stdout=output)

		users = get_user_model().objects.filter(username__in=DEFAULT_SUBADMIN_USERNAMES)
		self.assertEqual(users.count(), len(DEFAULT_SUBADMIN_USERNAMES))
		self.assertEqual(users.filter(is_staff=True, is_superuser=False).count(), len(DEFAULT_SUBADMIN_USERNAMES))
		self.assertEqual(mocked_input.call_count, len(DEFAULT_SUBADMIN_USERNAMES) * 2)

	@patch('builtins.input', return_value='unused')
	def test_does_not_downgrade_or_reset_existing_superuser(self, mocked_getpass):
		superuser = get_user_model().objects.create_superuser(
			username='site-owner',
			password='Original-strong-passphrase-52!',
			email='owner@example.com',
		)
		output = StringIO()

		call_command('create_subadmins', 'site-owner', stdout=output, stderr=output)

		superuser.refresh_from_db()
		self.assertTrue(superuser.is_superuser)
		self.assertTrue(superuser.check_password('Original-strong-passphrase-52!'))
		mocked_getpass.assert_not_called()

	@patch(
		'builtins.input',
		side_effect=['MsMathesonIl!201', 'MsMathesonIl!201'],
	)
	def test_create_ms_matheson_subadmin_creates_staff_account(self, mocked_getpass):
		output = StringIO()

		call_command('create_ms_matheson_subadmin', stdout=output)

		user = get_user_model().objects.get(username='MsMathesonIl')
		self.assertTrue(user.is_staff)
		self.assertFalse(user.is_superuser)
		self.assertTrue(user.check_password('MsMathesonIl!201'))
		self.assertEqual(user.first_name, 'Ms')
		self.assertEqual(user.last_name, 'Matheson')
		self.assertEqual(mocked_getpass.call_count, 2)


class GamePageTests(TestCase):
	def test_game_page_is_public_and_linked_in_nav(self):
		response = self.client.get(reverse('game'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Work in progress')
		self.assertContains(response, 'Pick your character')
		self.assertContains(response, 'data-character="eve"')
		self.assertContains(response, 'data-character="jim"')
		self.assertContains(response, 'DO YOU KNOW ABOUT HUNGER INSECURITY?')
		self.assertContains(response, 'Feed Nova Scotia')
		self.assertContains(response, f'href="{reverse("game")}"')


class QrCodePageTests(TestCase):
	def test_qr_code_page_is_public_and_linked_in_nav(self):
		response = self.client.get(reverse('qr_code'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'QR_Code')
		self.assertContains(response, f'href="{reverse("qr_code")}"')


class UpdatesPageTests(TestCase):
	def test_updates_page_is_public_and_linked_in_nav(self):
		response = self.client.get(reverse('updates'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Game')
		self.assertContains(response, 'phone')
		self.assertContains(response, 'QR code')
		self.assertContains(response, f'href="{reverse("updates")}"')


class CreateMainAdminCommandTests(TestCase):
	@patch(
		'core.management.commands.create_main_admin.getpass.getpass',
		side_effect=['Strong-Admin-Passphrase-83!', 'Strong-Admin-Passphrase-83!'],
	)
	@patch('builtins.input', return_value='site-owner')
	def test_creates_superuser_with_prompted_credentials(self, mocked_input, mocked_getpass):
		output = StringIO()

		call_command('create_main_admin', stdout=output)

		user = get_user_model().objects.get(username='site-owner')
		self.assertTrue(user.is_active)
		self.assertTrue(user.is_staff)
		self.assertTrue(user.is_superuser)
		self.assertTrue(user.check_password('Strong-Admin-Passphrase-83!'))
		self.assertNotIn('Strong-Admin-Passphrase-83!', output.getvalue())
		mocked_input.assert_called_once()
		self.assertEqual(mocked_getpass.call_count, 2)

	@patch('builtins.input', return_value='site-owner')
	def test_refuses_to_change_an_existing_account(self, mocked_input):
		user_model = get_user_model()
		existing_user = user_model.objects.create_user(
			username='site-owner',
			password='Existing-Password-83!',
		)
		output = StringIO()

		with self.assertRaises(CommandError):
			call_command('create_main_admin', stdout=output)

		existing_user.refresh_from_db()
		self.assertFalse(existing_user.is_superuser)
		self.assertTrue(existing_user.check_password('Existing-Password-83!'))


@override_settings(MULTIPLAYER_AVAILABLE=True)
class MultiplayerTests(TestCase):
	def setUp(self):
		self.now = timezone.now()
		self.clock = MultiplayerGameClock.objects.create(
			pk=1,
			started_at=self.now,
		)

	def create_player(self, name='Player'):
		return MultiplayerPlayer.objects.create(
			name=name,
			normalized_name=name.casefold(),
			password_hash='not-used-by-tests',
			balance=15,
			last_paid_day=0,
		)

	def test_multiplayer_page_offers_separate_game_mode_and_auth(self):
		response = self.client.get(reverse('game_multiplayer'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Create an account')
		self.assertContains(response, 'Singleplayer')
		self.assertContains(response, 'Multiplayer')

	def test_unauthenticated_session_is_a_normal_signed_out_response(self):
		response = self.client.get(reverse('multiplayer_session'))

		self.assertEqual(response.status_code, 200)
		self.assertFalse(response.json()['authenticated'])
		self.assertIsNone(response.json()['player'])

	def test_multiplayer_stays_disabled_until_redis_and_persistent_storage_exist(self):
		with override_settings(MULTIPLAYER_AVAILABLE=False):
			page = self.client.get(reverse('game_multiplayer'))
			register = self.client.post(
				reverse('multiplayer_auth'),
				data={
					'mode': 'register',
					'name': 'New Player',
					'password': 'Safe-password-123',
				},
				content_type='application/json',
			)

		self.assertContains(page, 'needs Railway Redis and a persistent database')
		self.assertEqual(register.status_code, 503)

	def test_player_names_block_offensive_words_and_allow_innocent_names(self):
		for name in ('f u c k', 'Sh1t', 'hell', 'fuuuck'):
			with self.subTest(name=name):
				self.assertIsNone(clean_player_name(name))

		for name in ('Akram', 'Dickens', 'Scunthorpe', 'Pakistan'):
			with self.subTest(name=name):
				self.assertEqual(clean_player_name(name), name)

	def test_registration_stores_hashed_password_and_normalizes_name_uniqueness(self):
		response = self.client.post(
			reverse('multiplayer_auth'),
			data={
				'mode': 'register',
				'name': 'Nova Player',
				'password': 'Safe-password-123',
				'avatar': 'jim',
			},
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		player = MultiplayerPlayer.objects.get()
		self.assertEqual(player.normalized_name, 'nova player')
		self.assertNotEqual(player.password_hash, 'Safe-password-123')
		self.assertTrue(check_password('Safe-password-123', player.password_hash))
		self.assertEqual(player.balance, 15)
		self.assertEqual(player.avatar, 'jim')
		self.assertEqual(self.client.session['multiplayer_player_id'], player.pk)

		duplicate = self.client.post(
			reverse('multiplayer_auth'),
			data={
				'mode': 'register',
				'name': 'NOVA PLAYER',
				'password': 'Different-password-456',
			},
			content_type='application/json',
		)
		self.assertEqual(duplicate.status_code, 409)

	def test_registration_saves_custom_character_choices_for_later_sign_ins(self):
		custom = {
			'hair': 'short',
			'hairColor': '#123456',
			'skin': '#c08040',
			'shirt': '#abcdef',
			'pants': '#102030',
			'shoes': '#f0e0d0',
			'shoulders': 2,
			'hat': True,
			'hatColor': '#987654',
		}
		response = self.client.post(
			reverse('multiplayer_auth'),
			data={
				'mode': 'register',
				'name': 'CustomPlayer',
				'password': 'Safe-password-123',
				'avatar': 'custom',
				'custom_character': custom,
			},
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		player = MultiplayerPlayer.objects.get()
		self.assertEqual(player.avatar, 'custom')
		self.assertEqual(player.custom_character, custom)
		self.assertEqual(response.json()['player']['custom_character'], custom)
		self.assertEqual(
			self.client.get(reverse('multiplayer_session')).json()['player']['custom_character'],
			custom,
		)

	def test_custom_character_config_rejects_invalid_colors_and_options(self):
		self.assertEqual(_custom_character_config({}), DEFAULT_CUSTOM_CHARACTER)
		self.assertIsNone(_custom_character_config({'shirt': 'url(bad-value)'}))
		self.assertIsNone(_custom_character_config({'hair': 'purple'}))
		self.assertIsNone(_custom_character_config({'shoulders': True}))
		self.assertIsNone(_custom_character_config({'hat': 'yes'}))

	def test_sign_in_requires_matching_password(self):
		player = self.create_player('Nova')
		player.password_hash = make_password('Correct-password-123')
		player.save(update_fields=('password_hash',))

		bad_response = self.client.post(
			reverse('multiplayer_auth'),
			data={'mode': 'login', 'name': 'NOVA', 'password': 'wrong-password'},
			content_type='application/json',
		)
		self.assertEqual(bad_response.status_code, 401)

		good_response = self.client.post(
			reverse('multiplayer_auth'),
			data={'mode': 'login', 'name': 'nova', 'password': 'Correct-password-123'},
			content_type='application/json',
		)
		self.assertEqual(good_response.status_code, 200)
		self.assertEqual(self.client.session['multiplayer_player_id'], player.pk)

	def test_day_and_three_bingo_rounds_follow_shared_five_minute_clock(self):
		self.assertEqual(game_timing(self.now)['phase'], 'day')
		self.assertEqual(
			game_timing(self.now + timedelta(seconds=300))['round_number'],
			1,
		)
		self.assertEqual(
			game_timing(self.now + timedelta(seconds=400))['round_number'],
			2,
		)
		self.assertEqual(
			game_timing(self.now + timedelta(seconds=500))['round_number'],
			3,
		)
		self.assertEqual(
			game_timing(self.now + timedelta(seconds=600))['phase'],
			'day',
		)

	def test_each_new_day_grants_fifteen_dollars_once(self):
		player = self.create_player()
		self.clock.started_at = self.now - timedelta(seconds=610)
		self.clock.save(update_fields=('started_at',))

		first = get_world_snapshot(player.pk, now=self.now)
		second = get_world_snapshot(player.pk, now=self.now + timedelta(seconds=2))

		player.refresh_from_db()
		self.assertEqual(first['phase'], 'day')
		self.assertEqual(player.balance, 15 + DAY_PAY)
		self.assertEqual(second['player']['balance'], 15 + DAY_PAY)

	def test_daytime_buy_and_feed_donation_update_all_time_score(self):
		player = self.create_player()
		presence = MultiplayerPresence.objects.create(
			connection_id=uuid.uuid4(),
			player=player,
			x=450,
		)

		bought = perform_action(presence.connection_id, 'buy', now=self.now)
		self.assertTrue(bought['ok'])
		self.assertEqual(bought['player']['balance'], 10)
		self.assertEqual(bought['player']['cans_held'], 1)

		MultiplayerPresence.objects.filter(pk=presence.pk).update(x=-450)
		donated = perform_action(presence.connection_id, 'donate', now=self.now)
		self.assertTrue(donated['ok'])
		self.assertEqual(donated['player']['cans_held'], 0)
		self.assertEqual(donated['player']['donated_cans'], 1)
		player.refresh_from_db()
		self.assertEqual(player.donated_cans, 1)

	def test_bingo_round_awards_soccer_ball_to_three_valid_winners(self):
		players = [self.create_player(f'Player {index}') for index in range(4)]
		self.clock.started_at = self.now - timedelta(seconds=590)
		self.clock.save(update_fields=('started_at',))
		with patch('core.multiplayer.bingo_calls', return_value=list(range(1, 76))):
			for player in players[:3]:
				result = claim_bingo(player.pk, round_number=3, now=self.now)
				self.assertTrue(result['ok'])
				self.assertEqual(result['player']['soccer_balls'], 1)

			too_late = claim_bingo(players[3].pk, round_number=3, now=self.now)

		self.assertFalse(too_late['ok'])
		self.assertEqual(
			MultiplayerBingoWinner.objects.filter(
				cycle_number=0,
				round_number=3,
			).count(),
			3,
		)
		self.assertEqual(
			set(MultiplayerBingoWinner.objects.values_list('winner_slot', flat=True)),
			{1, 2, 3},
		)

	def test_leaderboard_orders_all_players_by_total_donations(self):
		low = self.create_player('Low')
		high = self.create_player('High')
		low.donated_cans = 2
		low.save(update_fields=('donated_cans',))
		high.donated_cans = 9
		high.save(update_fields=('donated_cans',))

		response = self.client.get(reverse('multiplayer_leaderboard'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			[entry['name'] for entry in response.json()['players']],
			['High', 'Low'],
		)


class CreateSubadminCommandTests(TestCase):
	@patch(
		'core.management.commands.create_subadmin.getpass.getpass',
		side_effect=['Strong-Subadmin-Passphrase-83!', 'Strong-Subadmin-Passphrase-83!'],
	)
	@patch('builtins.input', return_value='event-helper')
	def test_creates_staff_only_account_with_prompted_credentials(
		self, mocked_input, mocked_getpass
	):
		output = StringIO()

		call_command('create_subadmin', stdout=output)

		user = get_user_model().objects.get(username='event-helper')
		self.assertTrue(user.is_active)
		self.assertTrue(user.is_staff)
		self.assertFalse(user.is_superuser)
		self.assertTrue(user.check_password('Strong-Subadmin-Passphrase-83!'))
		self.assertNotIn('Strong-Subadmin-Passphrase-83!', output.getvalue())
		mocked_input.assert_called_once()
		self.assertEqual(mocked_getpass.call_count, 2)

	@patch('builtins.input', return_value='event-helper')
	def test_refuses_to_change_an_existing_account(self, mocked_input):
		user_model = get_user_model()
		existing_user = user_model.objects.create_user(
			username='event-helper',
			password='Existing-Password-83!',
		)
		output = StringIO()

		with self.assertRaises(CommandError):
			call_command('create_subadmin', stdout=output)

		existing_user.refresh_from_db()
		self.assertFalse(existing_user.is_staff)
		self.assertFalse(existing_user.is_superuser)
		self.assertTrue(existing_user.check_password('Existing-Password-83!'))
