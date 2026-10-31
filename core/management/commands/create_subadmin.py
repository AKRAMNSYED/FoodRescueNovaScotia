import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import (
    UserAttributeSimilarityValidator,
    get_default_password_validators,
    validate_password,
)
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create a staff-only subadmin account, prompting for its credentials.'

    def handle(self, *args, **options):
        user_model = get_user_model()
        username = input('Username for subadmin: ').strip()
        if not username:
            raise CommandError('Username cannot be empty.')

        if user_model.objects.filter(username=username).exists():
            raise CommandError(
                f'User {username!r} already exists. Choose a new username; no account was changed.'
            )

        user = user_model(username=username)
        password_validators = [
            validator
            for validator in get_default_password_validators()
            if not isinstance(validator, UserAttributeSimilarityValidator)
        ]
        while True:
            password = getpass.getpass('Password for subadmin: ')
            confirmation = getpass.getpass('Confirm password: ')
            if password != confirmation:
                self.stderr.write(self.style.ERROR('Passwords do not match. Try again.'))
                continue

            try:
                validate_password(
                    password,
                    user=user,
                    password_validators=password_validators,
                )
            except ValidationError as error:
                self.stderr.write(self.style.ERROR(' '.join(error.messages)))
                continue
            break

        user_model.objects.create_user(
            username=username,
            password=password,
            is_staff=True,
            is_superuser=False,
        )
        self.stdout.write(self.style.SUCCESS(
            f'Subadmin {username!r} created with staff-only privileges.'
        ))
