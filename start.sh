#!/bin/sh
set -e

if [ -z "$DATABASE_URL" ] && [ -z "$RAILWAY_VOLUME_MOUNT_PATH" ]; then
  echo "WARNING: no Railway volume attached. The database lives on temporary storage and ALL ACCOUNTS ARE DELETED on every redeploy. Attach a volume (mount path /data)."
elif [ -n "$DATABASE_URL" ]; then
  echo "Using the configured SQL database for persistent account and game data."
else
  echo "Using persistent volume at $RAILWAY_VOLUME_MOUNT_PATH for the database."
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" hunger_insecurity_app.asgi:application