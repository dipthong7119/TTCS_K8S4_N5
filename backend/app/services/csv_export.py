"""Small streaming helpers shared by report CSV endpoints."""

import csv
from collections.abc import Iterable, Sequence
from io import StringIO

from fastapi.responses import StreamingResponse


def csv_stream(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> Iterable[str]:
    """Yield UTF-8 CSV text with a BOM and RFC-compatible quoting."""
    buffer = StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    yield "\ufeff"
    writer.writerow(headers)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


def csv_response(
    filename: str,
    headers: Sequence[str],
    rows: Iterable[Sequence[object]],
) -> StreamingResponse:
    """Build a downloadable UTF-8 CSV response from a lazy row iterator."""
    return StreamingResponse(
        csv_stream(headers, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
