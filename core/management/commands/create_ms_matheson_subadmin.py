from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import (
    UserAttributeSimilarityValidator,
    get_default_password_validators,
    validate_password,
)
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Create or update the Ms Matheson staff-only subadmin account.'

    def handle(self, *args, **options):
        username = 'MsMathesonIl'
        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()

        if user and user.is_superuser:
            self.stderr.write(self.style.ERROR(
                f'Skipping {username}: it is already a superuser.'
            ))
            return

        if user is None:
            user = user_model(username=username, first_name='Ms', last_name='Matheson')
        else:
            user.first_name = 'Ms'
            user.last_name = 'Matheson'

        while True:
            password = input(f'New password for {username} (visible): ')
            confirmation = input('Confirm password (visible): ')
            if password != confirmation:
                self.stderr.write(self.style.ERROR('Passwords do not match. Try again.'))
                continue

            password_validators = [
                validator
                for validator in get_default_password_validators()
                if not isinstance(validator, UserAttributeSimilarityValidator)
            ]
            try:
                validate_password(password, user=user, password_validators=password_validators)
            except ValidationError as error:
                self.stderr.write(self.style.ERROR(' '.join(error.messages)))
                continue
            break

        with transaction.atomic():
            user.is_active = True
            user.is_staff = True
            user.is_superuser = False
            user.set_password(password)
            user.save()

        self.stdout.write(self.style.SUCCESS(
            f'{username} is ready as a staff-only subadmin.'
        ))
