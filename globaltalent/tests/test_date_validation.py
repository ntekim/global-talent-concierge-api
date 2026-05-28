import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.doc_sentry import _parse_date, _validate_dates


def test_parse_date_yyyy_mm_dd():
    d = _parse_date("2024-01-15")
    assert d is not None
    assert d.year == 2024
    assert d.month == 1
    assert d.day == 15


def test_parse_date_mm_dd_yyyy():
    d = _parse_date("01/15/2024")
    assert d is not None
    assert d.month == 1
    assert d.day == 15


def test_parse_date_dd_mon_yyyy():
    d = _parse_date("15 Jan 2024")
    assert d is not None


def test_parse_date_empty():
    assert _parse_date("") is None


def test_parse_date_none():
    assert _parse_date(None) is None


def test_valid_dates_no_errors():
    result = _validate_dates({
        "issue_date": "2024-01-01",
        "expiry_date": "2028-01-01",
    })
    assert "date_errors" not in result
    assert "date_warnings" not in result


def test_future_issue_date_flagged():
    future = datetime.now(timezone.utc).replace(year=2030).strftime("%Y-%m-%d")
    result = _validate_dates({
        "issue_date": future,
        "expiry_date": "2035-01-01",
    })
    assert "date_errors" in result
    assert any("future" in e.lower() for e in result["date_errors"])


def test_expired_document_flagged():
    result = _validate_dates({
        "issue_date": "2020-01-01",
        "expiry_date": "2023-01-01",
    })
    assert "date_errors" in result
    assert any("expired" in e.lower() for e in result["date_errors"])


def test_expiry_before_issue_flagged():
    result = _validate_dates({
        "issue_date": "2025-01-01",
        "expiry_date": "2024-01-01",
    })
    assert "date_errors" in result
    assert any("before" in e.lower() for e in result["date_errors"])


def test_expiry_same_as_issue_flagged():
    result = _validate_dates({
        "issue_date": "2025-06-01",
        "expiry_date": "2025-06-01",
    })
    assert "date_errors" in result
    assert any("before" in e.lower() for e in result["date_errors"])


def test_expiry_within_6_months_warns():
    from datetime import timedelta
    five_months = datetime.now(timezone.utc) + timedelta(days=150)
    result = _validate_dates({
        "issue_date": "2020-01-01",
        "expiry_date": five_months.strftime("%Y-%m-%d"),
    })
    if "date_warnings" in result:
        assert any("6 months" in w.lower() for w in result["date_warnings"])
