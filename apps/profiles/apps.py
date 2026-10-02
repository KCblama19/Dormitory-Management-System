from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.profiles'
    
    def ready(self):
        # Force Django to execute the
        # custom model packages on boot
        import apps.profiles.student.models
        import apps.profiles.staff.models