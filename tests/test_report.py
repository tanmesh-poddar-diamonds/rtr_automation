import csv

from report import RingResult, format_summary, write_summary


def results():
    return [
        RingResult("A1", "Pear", "1.5", "done", downloaded=387, seconds=120.4),
        RingResult("A2", "Round", "1", "stalled", downloaded=10, failed=1, seconds=130.0),
    ]


def test_write_summary_columns_and_rows(tmp_path):
    p = tmp_path / "summary.csv"
    write_summary(results(), p)
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    assert list(rows[0].keys()) == ["sku", "shape", "carat", "status", "downloaded", "skipped", "failed", "seconds"]
    assert rows[0]["sku"] == "A1" and rows[0]["downloaded"] == "387" and rows[0]["seconds"] == "120.4"
    assert rows[1]["status"] == "stalled"


def test_format_summary_counts_by_status():
    text = format_summary(results())
    assert "2 ring(s)" in text and "done: 1" in text and "stalled: 1" in text
    assert "A2" in text
