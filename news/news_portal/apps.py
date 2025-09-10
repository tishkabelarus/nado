from django.apps import AppConfig


class NewsPortalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'news_portal'
    label = 'news_portal'

    def ready(self):
        import news_portal.signals