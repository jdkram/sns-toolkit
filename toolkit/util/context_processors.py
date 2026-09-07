from django.conf import settings


def venue(request):  # noqa: ARG001 -- context processor API
    return {
        "VENUE": settings.VENUE,
        "VERSION": settings.VERSION,
    }
