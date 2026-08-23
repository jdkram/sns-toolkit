from django.conf import settings


def venue(request):
    return {
        "VENUE": settings.VENUE,
        "MEMBERSHIP_EXPIRY_ENABLED": settings.MEMBERSHIP_EXPIRY_ENABLED,
    }
