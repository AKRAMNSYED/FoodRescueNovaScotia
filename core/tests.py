from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import ChangeProposal, Comment, Event


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
