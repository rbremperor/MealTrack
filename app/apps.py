from django.apps import AppConfig

class AppConfig(AppConfig):
    name = 'app'  # replace 'app' with your actual app name

    def ready(self):
        import app.signals  # import signals so they get registered
