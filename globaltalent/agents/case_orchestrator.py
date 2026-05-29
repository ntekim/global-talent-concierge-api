import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from logger import get_logger

from agents.doc_sentry import run as doc_sentry_run
from agents.compliance_agent import run as compliance_run, async_run as compliance_async_run
from agents.relocation_agent import run as relocation_run, async_run as relocation_async_run

log = get_logger("case_orchestrator")


def run_case(
    file_path: str,
    destination_country: str,
    destination_city: str,
    hire_profile: dict,
    auto_approve: bool = False,
) -> dict:
    t_total = time.perf_counter()

    try:
        log.info("STEP 1: DocSentry running...")
        document_data = doc_sentry_run(file_path)
    except Exception as e:
        elapsed = int((time.perf_counter() - t_total) * 1000)
        log.error("FAILED at step 1 -- %dms total: %s", elapsed, e)
        return {"final_status": "ERROR", "step": 1, "error": str(e)}

    try:
        log.info("STEP 2: ComplianceAgent running...")
        compliance_result = compliance_run(document_data, destination_country)
    except Exception as e:
        elapsed = int((time.perf_counter() - t_total) * 1000)
        log.error("FAILED at step 2 -- %dms total: %s", elapsed, e)
        return {"final_status": "ERROR", "step": 2, "error": str(e)}

    decision = _handle_approval(compliance_result, destination_country, document_data, auto_approve)
    if decision != "APPROVE":
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.info("HR Decision: REJECTED at %s", ts)
        print("CASE REJECTED BY HR. Stopping.")
        return {
            "final_status": "REJECTED",
            "document_data": document_data,
            "compliance_result": compliance_result,
            "relocation_guide": None,
        }

    try:
        log.info("STEP 3: RelocationAgent running...")
        relocation_guide = relocation_run(hire_profile)
    except Exception as e:
        elapsed = int((time.perf_counter() - t_total) * 1000)
        log.error("FAILED at step 3 -- %dms total: %s", elapsed, e)
        return {"final_status": "ERROR", "step": 3, "error": str(e)}

    print("\n--- RELOCATION GUIDE ---")
    print(relocation_guide)
    log.info("CASE COMPLETE. Notifying HR for awareness.")

    summary = {
        "final_status": "COMPLETED",
        "document_data": document_data,
        "compliance_result": compliance_result,
        "relocation_guide": relocation_guide,
    }
    print("\nFinal Case Summary:")
    print(json.dumps(summary, indent=2))

    elapsed = int((time.perf_counter() - t_total) * 1000)
    log.info("TOTAL CASE TIME: %dms (%.1fs)", elapsed, elapsed / 1000)
    return summary


async def run_case_async(
    file_path: str,
    destination_country: str,
    destination_city: str,
    hire_profile: dict,
    auto_approve: bool = True,
) -> dict:
    t_total = time.perf_counter()

    try:
        log.info("STEP 1: DocSentry running...")
        document_data = doc_sentry_run(file_path)
    except Exception as e:
        elapsed = int((time.perf_counter() - t_total) * 1000)
        log.error("FAILED at step 1 -- %dms total: %s", elapsed, e)
        return {"final_status": "ERROR", "step": 1, "error": str(e)}

    try:
        log.info("STEP 2: ComplianceAgent running...")
        compliance_result = await compliance_async_run(document_data, destination_country)
    except Exception as e:
        elapsed = int((time.perf_counter() - t_total) * 1000)
        log.error("FAILED at step 2 -- %dms total: %s", elapsed, e)
        return {"final_status": "ERROR", "step": 2, "error": str(e)}

    decision = _handle_approval(compliance_result, destination_country, document_data, auto_approve)
    if decision != "APPROVE":
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.info("HR Decision: REJECTED at %s", ts)
        return {
            "final_status": "REJECTED",
            "document_data": document_data,
            "compliance_result": compliance_result,
            "relocation_guide": None,
        }

    try:
        log.info("STEP 3: RelocationAgent running...")
        relocation_guide = await relocation_async_run(hire_profile)
    except Exception as e:
        elapsed = int((time.perf_counter() - t_total) * 1000)
        log.error("FAILED at step 3 -- %dms total: %s", elapsed, e)
        return {"final_status": "ERROR", "step": 3, "error": str(e)}

    log.info("CASE COMPLETE.")
    summary = {
        "final_status": "COMPLETED",
        "document_data": document_data,
        "compliance_result": compliance_result,
        "relocation_guide": relocation_guide,
    }
    elapsed = int((time.perf_counter() - t_total) * 1000)
    log.info("TOTAL CASE TIME: %dms (%.1fs)", elapsed, elapsed / 1000)
    return summary


def _handle_approval(
    compliance_result: dict,
    destination_country: str,
    document_data: dict,
    auto_approve: bool,
) -> str:
    full_name = document_data.get("full_name", "N/A")
    status = compliance_result.get("status", "N/A")
    score = compliance_result.get("confidence_score", "N/A")
    label = compliance_result.get("confidence_label", "N/A")
    reasons = compliance_result.get("reasons", [])
    missing = compliance_result.get("missing_documents", [])
    recommendation = compliance_result.get("recommendation", "")

    print("""
===============================
COMPLIANCE CHECK RESULT
===============================""")
    print(f"Candidate Name   : {full_name}")
    print(f"Destination      : {destination_country}")
    print(f"Status           : {status}")
    print(f"Confidence Score : {score}/100")
    print(f"Confidence Level : {label}")
    print("--------------------------------")
    print("Reasons          :")
    for r in reasons:
        print(f"  - {r}")
    print("--------------------------------")
    print("Missing Documents:")
    for m in missing:
        print(f"  - {m}")
    if not missing:
        print("  - None")
    print("--------------------------------")
    print(f"Recommendation   : {recommendation}")
    print("================================")

    if auto_approve:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log.info("Auto-approve enabled. Approving at %s", ts)
        print("AUTO-APPROVED (running in API mode)")
        return "APPROVE"

    print("ACTION REQUIRED: Type APPROVE to continue or REJECT to stop the case")
    decision = sys.stdin.readline().strip().upper()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("HR Decision: %s at %s", decision, ts)
    return decision
