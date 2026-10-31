import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create the main administrator account, prompting for its credentials.'

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = input('Username for main admin: ').strip()
        if not username:
            raise CommandError('Username cannot be empty.')

        if user_model.objects.filter(username=username).exists():
            raise CommandError(
                f'User {username!r} already exists. Choose a new username; no account was changed.'
            )

        user = user_model(username=username)
        while True:
            password = getpass.getpass('Password for main admin: ')
            confirmation = getpass.getpass('Confirm password: ')
            if password != confirmation:
                self.stderr.write(self.style.ERROR('Passwords do not match. Try again.'))
                continue

            try:
                validate_password(password, user=user)
            except ValidationError as error:
                self.stderr.write(self.style.ERROR(' '.join(error.messages)))
                continue
            break

        user_model.objects.create_superuser(
            username=username,
            email='',
            password=password,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Main admin {username!r} created with full administrator privileges.'
        ))
