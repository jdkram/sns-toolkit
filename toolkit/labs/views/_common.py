"""Labs views, split per feature.

Each submodule carries the original import header verbatim so every name
a view uses is available locally; the only genuinely cross-module helper
still local to this package is ``_feature_enabled_or_404``. ``_user_volunteer``
was promoted to ``toolkit.util.volunteers`` in Chunk 8 (deduplicate) — it's
re-exported here under its old private name so submodules and the package's
own ``__init__.py`` re-export list don't need touching. The package
re-exports every public name so ``urls.py`` (which does ``from . import
views``) and the one external importer (``toolkit/index/views.py`` pulls
``_unread_bulletins_for``) keep working unchanged.
"""

# human-contributors: ["Jonny Kram"]; ai-contributors: ["glm-5.2", "Claude Sonnet 5"]; status: "#ai-input"

from functools import wraps

from django.http import Http404

from toolkit.util.volunteers import user_volunteer as _user_volunteer

__all__ = ["_user_volunteer", "_feature_enabled_or_404"]


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
