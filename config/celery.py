import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("lifeos")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Beat schedule stays empty until the tasks it points at exist.
# SPEC 9 defines the target schedule; the 06:30-07:40 leg is a chain/chord so a
# late link never silently skips the 08:00 delivery. Populated from session 13.
app.conf.beat_schedule = {}
