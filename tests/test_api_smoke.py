import asyncio
import json
import time
import httpx

PORT = 18999


async def check(method, path, expected_status, body=None):
    start = time.perf_counter()
    async with httpx.AsyncClient() as client:
        if method == "GET":
            resp = await client.get(f"http://127.0.0.1:{PORT}{path}", timeout=10)
        else:
            resp = await client.post(f"http://127.0.0.1:{PORT}{path}", json=body or {}, timeout=10)
    elapsed = (time.perf_counter() - start) * 1000
    status = "PASS" if resp.status_code == expected_status else "FAIL"
    icon = "[OK]" if status == "PASS" else "[FAIL]"
    detail = ""
    try:
        data = resp.json()
        if isinstance(data, dict):
            s = json.dumps(data, default=str)
            if len(s) > 80:
                s = s[:77] + "..."
            detail = f" {s}"
    except Exception:
        detail = f" status={resp.status_code}"
    print(f"  {icon} {status:4}  {method:4} {path:<50} {elapsed:>7.1f}ms  (expected {expected_status}){detail}")
    return status == "PASS"


async def main():
    print("=" * 100)
    print("  GlobalTalent AI Agent — API Smoke Test with Latency")
    print("=" * 100)
    print()

    tests = [
        ("/health", "GET", 200, None),
        ("/api/cache/stats", "GET", 200, None),
        ("/api/cases", "GET", 200, None),
        ("/api/cases/nonexistent", "GET", 404, None),
        ("/api/cases/nonexistent/timeline", "GET", 404, None),
        ("/api/webhooks/maestro/case-status/nonexistent", "GET", 404, None),
        ("/api/slack/interactive", "POST", 400, {}),
        ("/api/webhooks/maestro/document-verify", "POST", 404, {"case_id": "nonexistent", "action": "verify", "payload": {}}),
        ("/api/webhooks/maestro/compliance-check", "POST", 404, {"case_id": "nonexistent", "action": "compliance", "payload": {}}),
        ("/api/webhooks/maestro/relocation-guide", "POST", 404, {"case_id": "nonexistent", "action": "relocation", "payload": {}}),
        ("/api/webhooks/maestro/hr-decision", "POST", 404, {"case_id": "nonexistent", "decision": "APPROVE", "reviewer_name": "Test"}),
        ("/docs", "GET", 200, None),
        ("/openapi.json", "GET", 200, None),
    ]

    passed = 0
    for path, method, expected, body in tests:
        try:
            ok = await check(method, path, expected, body)
            if ok:
                passed += 1
        except Exception as e:
            print(f"  [FAIL] {method:4} {path:<50}  ERROR: {e}")

    total = len(tests)
    print()
    print("=" * 100)
    print(f"  Results: {passed}/{total} passed" + ("  ALL GOOD!" if passed == total else ""))
    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
