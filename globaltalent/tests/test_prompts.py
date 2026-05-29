import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prompts import extraction_prompt, compliance_prompt, relocation_prompt


def test_extraction_prompt_contains_fields():
    prompt = extraction_prompt("some raw text")
    assert "full_name" in prompt
    assert "document_type" in prompt
    assert "document_number" in prompt
    assert "issue_date" in prompt
    assert "expiry_date" in prompt
    assert "nationality" in prompt
    assert "issuing_country" in prompt


def test_extraction_prompt_includes_text():
    prompt = extraction_prompt("RAW OCR TEXT HERE")
    assert "RAW OCR TEXT HERE" in prompt


def test_compliance_prompt_has_required_fields():
    doc_data = {"full_name": "John", "document_type": "PASSPORT"}
    prompt = compliance_prompt("visa context", "", doc_data)
    assert "PASS or FAIL" in prompt
    assert "confidence_score" in prompt
    assert "reasons" in prompt
    assert "missing_documents" in prompt
    assert "recommendation" in prompt


def test_compliance_prompt_includes_document_data():
    doc_data = {"full_name": "Alice", "document_type": "VISA"}
    prompt = compliance_prompt("ctx", "", doc_data)
    assert "Alice" in prompt
    assert "VISA" in prompt


def test_relocation_prompt_has_sections():
    profile = {"full_name": "Bob", "family_size": 2, "monthly_budget_usd": 4000, "destination_city": "Paris"}
    prompt = relocation_prompt(profile, "local info", "")
    assert "neighbourhoods" in prompt.lower()
    assert "schools" in prompt.lower()
    assert "living costs" in prompt.lower()
    assert "cultural tips" in prompt.lower()
    assert "30 day" in prompt.lower()


def test_relocation_prompt_addresses_by_name():
    profile = {"full_name": "Charlie", "family_size": 1, "monthly_budget_usd": 3000, "destination_city": "Tokyo"}
    prompt = relocation_prompt(profile, "info", "")
    assert "Charlie" in prompt
