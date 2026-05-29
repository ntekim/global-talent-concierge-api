import asyncio
import httpx

BASE_URL = "http://localhost:8000"


async def test_endpoint(name: str, method: str, path: str, payload: dict = None):
    url = f"{BASE_URL}{path}"
    try:
        async with httpx.AsyncClient() as client:
            if method == "POST":
                resp = await client.post(url, json=payload, timeout=30)
            else:
                resp = await client.get(url, timeout=30)
        if resp.status_code == 200:
            print(f"  {name} — SUCCESS")
        else:
            detail = resp.text[:200]
            print(f"  {name} — FAILED (status {resp.status_code}): {detail}")
        return resp
    except Exception as e:
        print(f"  {name} — FAILED (connection error): {e}")
        return None


async def upload_test_case():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BASE_URL}/api/cases",
            files={"files": ("passport_test.png", b"fake-image-data", "image/png")},
            data={
                "destination_country": "Germany",
                "destination_city": "Berlin",
                "full_name": "Alice Johnson",
                "family_size": "2",
                "monthly_budget_usd": "6000",
            },
            timeout=30,
        )
    return resp


async def main():
    print("=" * 60)
    print("  GlobalTalent — Maestro Webhook Test Suite")
    print("=" * 60)
    print()

    # 0. Health check
    print("[0] Health check")
    resp = await test_endpoint("health", "GET", "/health")
    if resp is None or resp.status_code != 200:
        print("\n  ERROR: Backend server not running on port 8000.\n  Start with: uvicorn server:app --port 8000")
        return
    print()

    # 1. Create test case
    print("[1] Creating test case via POST /api/cases")
    create_resp = await upload_test_case()
    if create_resp.status_code == 200:
        data = create_resp.json()
        case_id = data.get("case_id")
        print(f"  Case created — SUCCESS (case_id={case_id[:8]}...)\n")
    else:
        print(f"  Case creation — FAILED (status {create_resp.status_code})\n")
        print("  Using fake case_id for 404 tests below.\n")
        case_id = None

    # 2. POST /api/webhooks/maestro/document-verify
    print("[2] POST /api/webhooks/maestro/document-verify")
    await test_endpoint(
        "document-verify",
        "POST",
        "/api/webhooks/maestro/document-verify",
        {"case_id": case_id or "NONEXISTENT-ABC-001", "action": "verify", "payload": {}},
    )

    # 3. POST /api/webhooks/maestro/compliance-check
    print("[3] POST /api/webhooks/maestro/compliance-check")
    await test_endpoint(
        "compliance-check",
        "POST",
        "/api/webhooks/maestro/compliance-check",
        {
            "case_id": case_id or "NONEXISTENT-ABC-001",
            "action": "compliance",
            "payload": {
                "hire_profile": {
                    "full_name": "Alice Johnson",
                    "family_size": 2,
                    "monthly_budget_usd": 6000,
                    "destination_city": "Berlin",
                }
            },
        },
    )

    # 4. POST /api/webhooks/maestro/relocation-guide
    print("[4] POST /api/webhooks/maestro/relocation-guide")
    await test_endpoint(
        "relocation-guide",
        "POST",
        "/api/webhooks/maestro/relocation-guide",
        {
            "case_id": case_id or "NONEXISTENT-ABC-001",
            "action": "relocation",
            "payload": {
                "hire_profile": {
                    "full_name": "Alice Johnson",
                    "family_size": 2,
                    "monthly_budget_usd": 6000,
                    "destination_city": "Berlin",
                }
            },
        },
    )

    # 5. POST /api/webhooks/maestro/hr-decision (APPROVE)
    print("[5] POST /api/webhooks/maestro/hr-decision (APPROVE)")
    await test_endpoint(
        "hr-decision-approve",
        "POST",
        "/api/webhooks/maestro/hr-decision",
        {
            "case_id": case_id or "NONEXISTENT-ABC-001",
            "decision": "APPROVE",
            "reviewer_name": "Sarah Manager",
            "comments": "All documents verified and compliance passed.",
        },
    )

    # 6. POST /api/webhooks/maestro/hr-decision (REJECT)
    print("[6] POST /api/webhooks/maestro/hr-decision (REJECT)")
    await test_endpoint(
        "hr-decision-reject",
        "POST",
        "/api/webhooks/maestro/hr-decision",
        {
            "case_id": case_id or "NONEXISTENT-ABC-001",
            "decision": "REJECT",
            "reviewer_name": "Sarah Manager",
            "comments": "Missing employment verification documents.",
        },
    )

    # 7. POST /api/webhooks/maestro/case-status
    print("[7] POST /api/webhooks/maestro/case-status")
    resp = await test_endpoint(
        "case-status",
        "POST",
        "/api/webhooks/maestro/case-status",
        {"case_id": case_id or "NONEXISTENT-ABC-001", "action": "status", "payload": {}},
    )

    if resp and resp.status_code == 200 and case_id:
        data = resp.json()
        status = data.get("status", "?")
        stage = data.get("current_stage", "?")
        doc_count = len(data.get("documents", []))
        print(f"    -> case status={status}, stage={stage}, documents={doc_count}")

    print()
    print("=" * 60)
    print("  All tests completed.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
