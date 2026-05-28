import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.compliance_agent import interpret_confidence


def test_interpret_confidence_very_high():
    assert "VERY HIGH" in interpret_confidence(95)


def test_interpret_confidence_high():
    assert "HIGH CONFIDENCE" in interpret_confidence(75)

    assert "FAIL" not in interpret_confidence(75)


def test_interpret_confidence_moderate():
    assert "MODERATE" in interpret_confidence(60)


def test_interpret_confidence_low():
    assert "LOW CONFIDENCE" in interpret_confidence(40)


def test_interpret_confidence_very_low():
    assert "VERY LOW" in interpret_confidence(10)


def test_interpret_confidence_boundaries():
    assert "PASS" in interpret_confidence(90)
    assert "PASS" in interpret_confidence(70)
    assert "WARN" in interpret_confidence(50)
    assert "FAIL" in interpret_confidence(30)
    assert "FAIL" in interpret_confidence(0)
