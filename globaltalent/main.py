import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agents.case_orchestrator import run_case


if __name__ == "__main__":
    example = {
        "full_name": "John Doe",
        "family_size": 3,
        "monthly_budget_usd": 5000,
        "destination_city": "Berlin",
    }

    result = run_case(
        file_path="test_docs/test_passport.png",
        destination_country="Germany",
        destination_city="Berlin",
        hire_profile=example,
    )

    sys.exit(0 if result.get("final_status") in ("COMPLETED", "REJECTED") else 1)
