#!/bin/bash
python manage.py collectstatic --noinput
python manage.py migrate
python -m gunicorn seguimiento.wsgi:application --bind=0.0.0.0:8000
