"""WSGI config for primitives_testbed project."""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "primitives_testbed.settings")

application = get_wsgi_application()
