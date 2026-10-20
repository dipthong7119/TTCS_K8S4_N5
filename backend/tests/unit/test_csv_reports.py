"""CSV formatting guarantees shared by report exports."""

import csv
from io import StringIO

from app.services.csv_export import csv_response, csv_stream


def test_csv_stream_includes_utf8_bom_stable_newlines_and_escaped_fields():
    value = 'Station, "Main"\nEast'
    text = "".join(csv_stream(["name", "amount"], [[value, 12500]]))

    assert text.startswith("\ufeffname,amount\r\n")
    rows = list(csv.reader(StringIO(text.lstrip("\ufeff"), newline="")))
    assert rows == [["name", "amount"], [value, "12500"]]


def test_csv_response_sets_download_headers():
    response = csv_response("report-2026.csv", ["date"], [["2026-10-19"]])

    assert response.media_type == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == 'attachment; filename="report-2026.csv"'
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
