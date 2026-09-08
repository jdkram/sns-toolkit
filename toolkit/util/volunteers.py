# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-input"
"""Shared volunteer-lookup helper.

Promoted from toolkit/labs/views/_common.py per QUALITY_PASS.md Chunk 8 —
toolkit/operations/views/maintenance.py carried a byte-for-byte duplicate
of the same function.
"""


def user_volunteer(user):
    """Return user.volunteer if the user has an associated Volunteer row, else None.

    Uses hasattr (the canonical Django pattern) rather than try/except, which
    would silently swallow real errors — e.g. a corrupt Volunteer row raising
    a database error would read as "no volunteer" and hide the bug.
    """
    return user.volunteer if hasattr(user, "volunteer") else None
