# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]
"""
inductions/views.py was split into this package in September 2026. Each
submodule owns one feature area; no
`_common.py` re-export hub, no shared import header — every submodule
imports only what it uses. This __init__ re-exports every view function
by name so `urls.py`'s `views.<name>` attribute access, and the two test
modules importing `_create_volunteer_from_signup` directly, keep working
unchanged.
"""

from .access_needs import (
    manage_access_needs_detail,
    manage_access_needs_list,
)
from .export import manage_export_csv
from .manage_settings import (
    manage_mark_policy_updated,
    manage_send_test_email,
    manage_settings,
)
from .public import (
    access_needs_signup,
    access_needs_thanks,
    calendar_ics,
    session_list_public,
    signup,
    signup_thanks,
)
from .sessions import (
    manage_session_close,
    manage_session_detail,
    manage_session_edit,
    manage_session_list,
    manage_session_new,
    manage_session_purge,
    manage_session_set_cap,
)
from .signups import (
    _create_volunteer_from_signup,
    manage_add_walkin,
    manage_check_in,
    manage_create_accounts,
    manage_edit_signup,
    manage_link_existing,
    manage_mark_attendance,
    manage_no_show,
    manage_remove_signup,
)

__all__ = [
    "access_needs_signup",
    "access_needs_thanks",
    "calendar_ics",
    "manage_access_needs_detail",
    "manage_access_needs_list",
    "manage_add_walkin",
    "manage_check_in",
    "manage_create_accounts",
    "manage_edit_signup",
    "manage_export_csv",
    "manage_link_existing",
    "manage_mark_attendance",
    "manage_mark_policy_updated",
    "manage_no_show",
    "manage_remove_signup",
    "manage_send_test_email",
    "manage_session_close",
    "manage_session_detail",
    "manage_session_edit",
    "manage_session_list",
    "manage_session_new",
    "manage_session_purge",
    "manage_session_set_cap",
    "manage_settings",
    "session_list_public",
    "signup",
    "signup_thanks",
    # re-exported for direct test-module imports, not URL-routed
    "_create_volunteer_from_signup",
]
