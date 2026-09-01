# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""Tags any email sent during a web request with who was logged in.

Sits alongside AuthenticationMiddleware in MIDDLEWARE so request.user is
already resolved. Sends from management commands or mailerd aren't requests
at all, so they set their own trigger_source explicitly (see
toolkit.audit.models.email_trigger) rather than going through this.
"""
from .models import email_trigger


class EmailTriggerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        user = user if user and user.is_authenticated else None
        with email_trigger("Web request", user=user):
            return self.get_response(request)
