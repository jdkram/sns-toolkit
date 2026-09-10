from django.test import TestCase
from django.utils import timezone

from toolkit.mailer.models import MailoutJob


class DoSendingProgressPct(TestCase):
    """do_sending()'s +1 nudge (so 0 sent shows 1%, not a stalled-looking
    0%) used to push the final batch to 101% unconditionally, normally
    masked by do_complete() resetting to exactly 100 -- but visible if the
    job dies before that runs."""

    def _job(self):
        return MailoutJob(
            subject="s",
            body_text="b",
            send_html=False,
            send_at=timezone.now(),
        )

    def test_zero_sent_shows_one_percent_not_zero(self):
        job = self._job()
        job.do_sending(sent=0, total=100)
        self.assertEqual(job.progress_pct, 1)

    def test_final_batch_caps_at_100_not_101(self):
        job = self._job()
        job.do_sending(sent=100, total=100)
        self.assertEqual(job.progress_pct, 100)

    def test_partial_progress_unaffected_by_the_cap(self):
        job = self._job()
        job.do_sending(sent=50, total=100)
        self.assertEqual(job.progress_pct, 51)

    def test_zero_total_reports_100(self):
        job = self._job()
        job.do_sending(sent=0, total=0)
        self.assertEqual(job.progress_pct, 100)
