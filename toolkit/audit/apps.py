# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
from django.apps import AppConfig


class AuditConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "toolkit.audit"

    def ready(self):
        # Side-effect import: connects the Event pre_delete hook.
        from . import signals  # noqa: F401
