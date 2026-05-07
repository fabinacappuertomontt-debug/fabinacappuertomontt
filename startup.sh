#!/bin/bash
export PYTHONPATH="/home/site/wwwroot/.python_packages/lib/site-packages:$PYTHONPATH"

python manage.py collectstatic --noinput

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    python manage.py migrate --noinput
fi

exec python -m gunicorn seguimiento.wsgi:application --bind=0.0.0.0:${PORT:-8000}
