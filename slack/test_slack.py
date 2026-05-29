import httpx
import asyncio
import sys

BASE_URL = "http://localhost:8001"


async def test_endpoint(name: str, endpoint: str, payload: dict):
    url = f"{BASE_URL}{endpoint}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"  {name} — SUCCESS")
            else:
                print(f"  {name} — FAILED (status {resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"   {name} — FAILED (connection error): {e}")


async def main():
    print("=" * 60)
    print("  GlobalTalent Slack Notifier — Test Suite")
    print("=" * 60)
    print()

    # 1. case-created
    print("[1/7] POST /notify/case-created")
    await test_endpoint("case-created", "/notify/case-created", {
        "case_id": "CASE-2026-001",
        "full_name": "Alice Johnson",
        "destination_city": "London",
        "destination_country": "United Kingdom",
        "document_type": "Work Visa"
    })

    # 2. compliance-pass
    print("[2/7] POST /notify/compliance-pass")
    await test_endpoint("compliance-pass", "/notify/compliance-pass", {
        "case_id": "CASE-2026-001",
        "full_name": "Alice Johnson",
        "destination_country": "United Kingdom",
        "confidence_score": 92,
        "confidence_label": "High"
    })

    # 3. compliance-fail
    print("[3/7] POST /notify/compliance-fail")
    await test_endpoint("compliance-fail", "/notify/compliance-fail", {
        "case_id": "CASE-2026-002",
        "full_name": "Bob Smith",
        "destination_country": "Germany",
        "confidence_score": 34,
        "confidence_label": "Low",
        "reasons": "Missing employment verification, address history incomplete",
        "missing_documents": "Bank statements (last 6 months), Employment letter",
        "recommendation": "Request documents from candidate and re-submit for review"
    })

    # 4. hr-approved
    print("[4/7] POST /notify/hr-approved")
    await test_endpoint("hr-approved", "/notify/hr-approved", {
        "case_id": "CASE-2026-001",
        "full_name": "Alice Johnson",
        "hr_name": "Sarah Manager",
        "timestamp": "2026-05-26 14:30 UTC"
    })

    # 5. hr-rejected
    print("[5/7] POST /notify/hr-rejected")
    await test_endpoint("hr-rejected", "/notify/hr-rejected", {
        "case_id": "CASE-2026-002",
        "full_name": "Bob Smith",
        "hr_name": "Sarah Manager",
        "timestamp": "2026-05-26 14:45 UTC",
        "recommendation": "Candidate needs to provide updated address proof"
    })

    # 6. relocation-ready
    print("[6/7] POST /notify/relocation-ready")
    await test_endpoint("relocation-ready", "/notify/relocation-ready", {
        "case_id": "CASE-2026-001",
        "full_name": "Alice Johnson",
        "destination_city": "London"
    })

    # 7. case-error
    print("[7/7] POST /notify/case-error")
    await test_endpoint("case-error", "/notify/case-error", {
        "case_id": "CASE-2026-003",
        "full_name": "Charlie Brown",
        "error_message": "Document processing service timeout after 30 seconds"
    })

    print()
    print("=" * 60)
    print("  All tests completed.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
