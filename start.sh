#!/bin/sh
set -e

if [ -z "$RAILWAY_VOLUME_MOUNT_PATH" ]; then
  echo "WARNING: no Railway volume attached. The database lives on temporary storage and ALL ACCOUNTS ARE DELETED on every redeploy. Attach a volume (mount path /data)."
else
  echo "Using persistent volume at $RAILWAY_VOLUME_MOUNT_PATH for the database."
fi

python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn hunger_insecurity_app.wsgi:application --bind "0.0.0.0:${PORT:-8000}"