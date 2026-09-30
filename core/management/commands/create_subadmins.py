from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Create or update staff-only accounts, prompting securely for passwords.'

    def add_arguments(self, parser):
        parser.add_argument('usernames', nargs='+')

    def handle(self, *args, **options):
        user_model = get_user_model()
        for username in dict.fromkeys(options['usernames']):
            user = user_model.objects.filter(username=username).first()
            if user and user.is_superuser:
                self.stderr.write(self.style.ERROR(
                    f'Skipping {username}: it is already a superuser.'
                ))
                continue

            if user is None:
                user = user_model(username=username)

            while True:
                password = input(f'New password for {username} (visible): ')
                confirmation = input('Confirm password (visible): ')
                if password != confirmation:
                    self.stderr.write(self.style.ERROR('Passwords do not match. Try again.'))
                    continue
                try:
                    validate_password(password, user=user)
                except ValidationError as error:
                    self.stderr.write(self.style.ERROR(' '.join(error.messages)))
                    continue
                break

            with transaction.atomic():
                user.is_active = True
                user.is_staff = True
                user.set_password(password)
                user.save()

            self.stdout.write(self.style.SUCCESS(f'{username} is ready as a staff-only subadmin.'))