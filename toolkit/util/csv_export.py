# human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-input"
"""Shared CSV-download response builder.

QUALITY_PASS.md Chunk 8: three views (members/views/volunteer_export.py,
inductions/views/export.py, diary/edit_views/reports.py) each hand-rolled
an HttpResponse + csv.writer pair. Only the inductions one guarded against
formula injection (a leading =, +, - or @ being interpreted as a formula
by the spreadsheet app that opens the file); the other two exported
member-supplied free text (names, notes, addresses) with no guard at all.
Unifying onto one helper closes that gap for all three at once.
"""

import csv

from django.http import HttpResponse


def csv_formula_guard(value):
    """Prefix a leading `=`/`+`/`-`/`@` with a tab so spreadsheet apps treat
    the cell as text rather than executing it as a formula on open.

    Non-string values (None, numbers) pass through unchanged.
    """
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return "\t" + value
    return value


def csv_response(filename, header, rows):
    """Build a text/csv HttpResponse with an attachment Content-Disposition.

    `header` is a list of column names (or None to omit the header row).
    `rows` is an iterable of iterables of cell values; every cell is passed
    through `csv_formula_guard` before being written.
    """
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    if header is not None:
        writer.writerow(header)
    for row in rows:
        writer.writerow([csv_formula_guard(cell) for cell in row])
    return response
