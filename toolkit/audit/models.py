# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude"]; status: "#ai-written"
"""
Durable audit records: sent emails (9.156) and deletions (9.159).

Both models answer "what happened?" questions for organisers without server
access. Log lines rotate away with the container; these rows persist until
the retention purge (purge_audit_logs command, driven by the
email_log_retain_days / deletion_log_retain_days SiteConfiguration fields).
"""
import logging
import threading
from contextlib import contextmanager

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class SentEmailLog(models.Model):
    """One row per email send attempt, written by LoggingEmailBackend.

    Deliberately body-free: bodies hold personal content and live
    password-set links. Mailout batches are summarised as one row (see
    summarise_email_batch), not one per recipient.
    """

    sent_at = models.DateTimeField(auto_now_add=True, db_index=True)
    recipients = models.TextField(help_text="Comma-joined; usually one address")
    subject = models.CharField(max_length=255)
    success = models.BooleanField()
    error = models.TextField(blank=True)
    backend = models.CharField(max_length=128)
    trigger_source = models.CharField(
        max_length=255,
        blank=True,
        help_text="What set this send off, e.g. 'Web request', "
        "'Scheduled job: send_volunteer_digest', 'Mailout job #42'",
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="The logged-in user whose action caused this send, if any",
    )

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        state = "sent" if self.success else "FAILED"
        return f"{self.sent_at:%Y-%m-%d %H:%M} {state}: '{self.subject}' to {self.recipients}"


class DeletionLog(models.Model):
    """One row per destructive action, written explicitly from deletion views.

    Not populated via pre_delete signals as the primary mechanism: seed and
    reseed commands mass-delete thousands of rows and would flood the table.
    """

    VIA_EDIT_UI = "edit-ui"
    VIA_MANAGEMENT_COMMAND = "management-command"
    VIA_CASCADE = "cascade"
    VIA_SIGNAL = "signal"
    VIA_CHOICES = [
        (VIA_EDIT_UI, "Edit UI"),
        (VIA_MANAGEMENT_COMMAND, "Management command"),
        (VIA_CASCADE, "Cascade"),
        (VIA_SIGNAL, "Signal (unexpected path)"),
    ]

    deleted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    model = models.CharField(max_length=64)
    object_pk = models.CharField(max_length=64)
    description = models.TextField(
        help_text="The object's str() plus key context, e.g. event name and showing date"
    )
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    via = models.CharField(max_length=32, choices=VIA_CHOICES)

    class Meta:
        ordering = ["-deleted_at"]

    def __str__(self):
        return f"{self.deleted_at:%Y-%m-%d %H:%M} {self.model} pk={self.object_pk}: {self.description}"


def log_deletion(model, object_pk, description, deleted_by=None, via=DeletionLog.VIA_EDIT_UI):
    """Write a DeletionLog row; never let a logging failure break the deletion."""
    try:
        DeletionLog.objects.create(
            model=model,
            object_pk=str(object_pk),
            description=description,
            deleted_by=deleted_by,
            via=via,
        )
    except Exception:
        logger.exception(
            f"Failed to write DeletionLog row for {model} pk={object_pk}"
        )


# --- Trigger tracking ------------------------------------------------------
#
# LoggingEmailBackend sits below every send call in the codebase and has no
# idea who or what asked for it. Callers announce themselves by setting a
# thread-local "current trigger" before sending: EmailTriggerMiddleware does
# this automatically for web requests (source="Web request", user=
# request.user), and management commands / mailerd wrap their run in
# email_trigger() explicitly. record_email() reads whatever is current.

_trigger_state = threading.local()


@contextmanager
def email_trigger(source, user=None):
    """Mark the reason for any email sent inside this block.

    Nests: a narrower call (e.g. inside a specific command) overrides an
    outer one for its duration, then the outer one is restored.
    """
    previous = getattr(_trigger_state, "current", None)
    _trigger_state.current = (source, user)
    try:
        yield
    finally:
        _trigger_state.current = previous


def _current_trigger():
    source, user = getattr(_trigger_state, "current", None) or (None, None)
    return source or "", user


def set_email_trigger(source, user=None):
    """One-shot variant of email_trigger() for management commands.

    Each command invocation is a fresh process (run via cron/systemd timer,
    not a long-lived worker), so there's nothing to restore afterwards --
    unlike email_trigger(), this doesn't need a matching exit.
    """
    _trigger_state.current = (source, user)


# --- Email batch summarisation -------------------------------------------
#
# A 500-member mailout must not create 500 SentEmailLog rows. The mailout
# sender wraps its loop in summarise_email_batch(); while the thread-local
# flag is set, record_email() accumulates counts instead of writing rows,
# and one summary row is written when the batch closes. Thread-local because
# mailerd and gunicorn workers each send on their own thread.

_batch_state = threading.local()


def record_email(recipients, subject, success, error="", backend=""):
    """Write a SentEmailLog row (or count it into the active batch).

    Called from LoggingEmailBackend after each message. Must never raise:
    a failure to write the audit row cannot be allowed to block the send.
    """
    trigger_source, triggered_by = _current_trigger()
    try:
        batch = getattr(_batch_state, "current", None)
        if batch is not None:
            batch["count"] += 1
            if not success:
                batch["failures"] += 1
                batch["last_error"] = error
            batch["backend"] = backend
            batch["trigger_source"] = trigger_source
            batch["triggered_by"] = triggered_by
            return
        SentEmailLog.objects.create(
            recipients=recipients,
            subject=subject[:255],
            success=success,
            error=error,
            backend=backend,
            trigger_source=trigger_source,
            triggered_by=triggered_by,
        )
    except Exception:
        logger.exception("Failed to write SentEmailLog row")


@contextmanager
def summarise_email_batch(subject):
    """Collapse all sends inside the block into one SentEmailLog summary row."""
    _batch_state.current = {
        "count": 0,
        "failures": 0,
        "last_error": "",
        "backend": "",
        "trigger_source": "",
        "triggered_by": None,
    }
    try:
        yield
    finally:
        batch = _batch_state.current
        _batch_state.current = None
        try:
            if batch["count"]:
                SentEmailLog.objects.create(
                    recipients=f"(mailout batch: {batch['count']} recipients)",
                    subject=subject[:255],
                    success=batch["failures"] == 0,
                    error=(
                        f"{batch['failures']} of {batch['count']} sends failed. "
                        f"Last error: {batch['last_error']}"
                        if batch["failures"]
                        else ""
                    ),
                    backend=batch["backend"],
                    trigger_source=batch["trigger_source"],
                    triggered_by=batch["triggered_by"],
                )
        except Exception:
            logger.exception("Failed to write mailout batch SentEmailLog row")
