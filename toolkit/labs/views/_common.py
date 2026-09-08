"""Labs views, split per feature.

Each submodule carries the original import header verbatim so every name
a view uses is available locally; the only genuinely cross-module helpers
(``_user_volunteer``, ``_feature_enabled_or_404``) live here. The package
re-exports every public name so ``urls.py`` (which does ``from . import
views``) and the one external importer (``toolkit/index/views.py`` pulls
``_unread_bulletins_for``) keep working unchanged.
"""

# human-contributors: ["Jonny Kram"]; ai-contributors: ["glm-5.2", "Claude Sonnet 5"]; status: "#ai-input"

from functools import wraps

from django.http import Http404


def _user_volunteer(user):
    """Return user.volunteer if the user has an associated Volunteer row, else None.

    Uses hasattr (the canonical Django pattern) rather than try/except, which
    would silently swallow real errors — e.g. a corrupt Volunteer row raising
    a database error would read as "no volunteer" and hide the bug.
    Replaces 11 bare `except Exception:` blocks across collectives + shopping
    views that had drifted to swallow all errors.
    """
    return user.volunteer if hasattr(user, "volunteer") else None


def _feature_enabled_or_404(flag_name):
    """404 a view unless the named SiteConfiguration boolean is True.

    Mirrors the pattern community_exchange_enabled originally used inline
    in exchange.py, generalised so each labs mini-tool can carry its own
    on/off switch without repeating the same three lines per view.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            from toolkit.diary.models import get_site_config

            if not getattr(get_site_config(), flag_name):
                raise Http404
            return func(request, *args, **kwargs)

        return wrapper

    return decorator
