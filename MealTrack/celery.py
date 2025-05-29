import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'MealTrack.settings')

app = Celery('MealTrack')

# Load settings with CELERY namespace to avoid conflicts
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover tasks.py in your apps
app.autodiscover_tasks()

# Set timezone for scheduled tasks (adjust as needed)
app.conf.timezone = 'UTC'  # or e.g. 'Asia/Tashkent'

# Define periodic task schedule (runs every midnight)
app.conf.beat_schedule = {
    'update-dashboard-regularly': {
        'task': 'app.tasks.update_dashboard_cache',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
}