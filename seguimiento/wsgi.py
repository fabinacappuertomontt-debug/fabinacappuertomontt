import os
from pathlib import Path

from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "seguimiento.settings")

application = get_wsgi_application()
base_dir = Path(__file__).resolve().parent.parent
application = WhiteNoise(application)
application.add_files(str(base_dir / "static"), prefix="static/")
staticfiles_dir = base_dir / "staticfiles"
if staticfiles_dir.exists():
    application.add_files(str(staticfiles_dir), prefix="static/")
