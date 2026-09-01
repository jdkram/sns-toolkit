# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""
Belt-and-braces deletion trap for Event (9.159).

Event.delete() raises IntegrityError by design, so single-instance deletion
through the UI is impossible -- but queryset .delete() bypasses that guard
(this is how the live "missing event" incident probably happened, via the
old branch's Django admin bulk delete). Any Event deletion reaching this
signal is therefore unexpected and worth a WARNING plus a DeletionLog row.

Seed/reseed commands legitimately mass-delete events; they set
suppress_event_deletion_log() around the wipe so the table isn't flooded
(the demo homeserver reseeds every 3 days).
"""
import logging
import threading
import traceback
from contextlib import contextmanager

from django.db.models.signals import pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)

_state = threading.local()


@contextmanager
def suppress_event_deletion_log():
    """Disable the Event deletion trap for a legitimate bulk wipe (seeding)."""
    _state.suppressed = True
    try:
        yield
    finally:
        _state.suppressed = False


@receiver(pre_delete, sender="diary.Event", dispatch_uid="audit_event_pre_delete")
def _log_event_deletion(sender, instance, **kwargs):
    if getattr(_state, "suppressed", False):
        return
    # Last three app-level stack frames, so the log shows which code path
    # bypassed the Event.delete() guard.
    stack = "".join(traceback.format_stack(limit=6)[:-1])[-1000:]
    logger.warning(
        f"Event pk={instance.pk} ('{instance.name}') is being DELETED. "
        f"Event deletion bypasses the model guard and should be near-impossible; "
        f"investigate. Stack tail:\n{stack}"
    )
    from .models import DeletionLog, log_deletion

    log_deletion(
        model="Event",
        object_pk=instance.pk,
        description=f"Event '{instance.name}' (guard-bypassing delete; see log for stack)",
        deleted_by=None,
        via=DeletionLog.VIA_SIGNAL,
    )
