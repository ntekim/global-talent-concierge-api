import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.doc_sentry import run, FALLBACK_DICT, CRITICAL_FIELDS, _clean_text


@patch("agents.doc_sentry._parse_with_openai")
@patch("agents.doc_sentry._ocr_image")
def test_extracts_fields_from_image(mock_ocr, mock_parse):
    mock_ocr.return_value = "PASSPORT JOHN DOE USA"
    mock_parse.return_value = {
        "full_name": "John Doe",
        "document_type": "PASSPORT",
        "document_number": "AB123456",
        "issue_date": "2020-01-01",
        "expiry_date": "2030-01-01",
        "nationality": "USA",
        "issuing_country": "United States",
    }

    result = run("test_docs/test_passport.png")

    assert result["full_name"] == "John Doe"
    assert result["document_type"] == "PASSPORT"
    assert result["document_number"] == "AB123456"
    assert result["nationality"] == "USA"
    assert "_warnings" not in result


@patch("agents.doc_sentry._parse_with_openai")
@patch("agents.doc_sentry._ocr_image")
def test_returns_error_for_empty_ocr(mock_ocr, mock_parse):
    mock_ocr.return_value = "   "

    result = run("test_docs/test_passport.png")

    assert result["error"] == "No text extracted from document"
    assert all(v is None for k, v in result.items() if k not in ("error", "_warnings"))


def test_returns_error_for_unsupported_file():
    result = run("test_docs/test_passport.txt")

    assert "error" in result
    assert "Unsupported" in result["error"]


def test_fallback_dict_has_all_keys():
    expected = {
        "full_name", "document_type", "document_number",
        "issue_date", "expiry_date", "nationality", "issuing_country",
    }
    assert set(FALLBACK_DICT.keys()) == expected


def test_critical_fields_defined():
    assert "full_name" in CRITICAL_FIELDS
    assert "document_type" in CRITICAL_FIELDS
    assert "document_number" in CRITICAL_FIELDS


@patch("agents.doc_sentry._parse_with_openai")
@patch("agents.doc_sentry._extract_pdf_text")
def test_pdf_tries_direct_extraction_first(mock_extract, mock_parse, tmp_path):
    mock_extract.return_value = "Some extracted text"
    mock_parse.return_value = {
        "full_name": "Jane Doe",
        "document_type": "VISA",
        "document_number": "VI789",
        "issue_date": None,
        "expiry_date": None,
        "nationality": None,
        "issuing_country": "Canada",
    }

    pdf = tmp_path / "test.pdf"
    pdf.write_text("dummy")

    result = run(str(pdf))

    assert result["full_name"] == "Jane Doe"
    assert result["document_type"] == "VISA"
    mock_extract.assert_called_once()


def test_clean_text_collapses_newlines():
    assert _clean_text("a\n\n\n\nb") == "a\n\nb"


def test_clean_text_strips_whitespace():
    assert _clean_text("  hello world  ") == "hello world"


def test_clean_text_normalizes_spaces():
    assert _clean_text("hello    world") == "hello world"


def test_clean_text_removes_non_printable():
    raw = "hello\x00world\x01test"
    cleaned = _clean_text(raw)
    assert "\x00" not in cleaned
    assert "\x01" not in cleaned


def test_clean_text_empty_returns_empty():
    assert _clean_text("") == ""
    assert _clean_text("   ") == ""
