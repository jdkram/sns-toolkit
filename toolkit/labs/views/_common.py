"""Labs views, split per feature.

Each submodule carries the original import header verbatim so every name
a view uses is available locally; the only genuinely cross-module helper
(``_user_volunteer``) lives here. The package re-exports every public name
so ``urls.py`` (which does ``from . import views``) and the one external
importer (``toolkit/index/views.py`` pulls ``_unread_bulletins_for``) keep
working unchanged.
"""

# human-contributors: ["Jonny Kram"]; ai-contributors: ["glm-5.2"]; status: "#ai-input"






def _user_volunteer(user):
    """Return user.volunteer if the user has an associated Volunteer row, else None.

    Uses hasattr (the canonical Django pattern) rather than try/except, which
    would silently swallow real errors — e.g. a corrupt Volunteer row raising
    a database error would read as "no volunteer" and hide the bug.
    Replaces 11 bare `except Exception:` blocks across collectives + shopping
    views that had drifted to swallow all errors.
    """
    return user.volunteer if hasattr(user, "volunteer") else None
