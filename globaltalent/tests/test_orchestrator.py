import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.case_orchestrator import _handle_approval


@patch("builtins.print")
def test_auto_approve_returns_approve(mock_print):
    result = _handle_approval(
        compliance_result={"status": "PASS", "confidence_score": 85},
        destination_country="Germany",
        document_data={"full_name": "John Doe"},
        auto_approve=True,
    )
    assert result == "APPROVE"


@patch("agents.case_orchestrator.run_case")
def test_run_case_returns_dict(mock_run):
    mock_run.return_value = {"final_status": "COMPLETED"}
    result = mock_run("test.png", "Germany", "Berlin", {"full_name": "X"}, auto_approve=True)
    assert result["final_status"] == "COMPLETED"


def test_handle_approval_auto_skips_stdin():
    result = _handle_approval(
        compliance_result={"status": "FAIL", "confidence_score": 30},
        destination_country="UK",
        document_data={"full_name": "Alice"},
        auto_approve=True,
    )
    assert result == "APPROVE"
