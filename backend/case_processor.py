import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings
from backend.database import (
    get_case_async, update_case_async, insert_document_async,
    update_document_async, record_stage, get_case_documents_async, get_case_stages_async,
)
from backend.services.cache import compliance_cache
from backend.slack_notifier import send_slack_notification, notify_manager_slack
from backend.utils.sse import set_progress, cleanup_progress
from logger import get_logger

log = get_logger("case_processor")
POLL_TIMEOUT = 28800


async def _await_hr_decision(case_id: str, poll_interval: int = 5, timeout: int = POLL_TIMEOUT):
    start = time.time()
    while time.time() - start < timeout:
        case = await get_case_async(case_id)
        if case:
            status = case.get("status")
            if status in ("COMPLETED", "ERROR", "REJECTED"):
                return True
            current_stage = case.get("current_stage", "")
            if current_stage not in ("manual_review", "compliance_remediation", "hr_review"):
                return True
        await asyncio.sleep(poll_interval)
    await update_case_async(case_id, current_stage="escalated", status="ESCALATED")
    await record_stage(case_id, "escalated", "system", "HR decision timeout - escalated")
    await notify_manager_slack(case_id, f"Case {case_id[:8]} was escalated due to decision timeout.")
    return False


async def process_case(case_id: str, file_paths: list[str], destination_country: str, destination_city: str, hire_profile: dict):
    try:
        await set_progress(case_id, {"status": "PROCESSING", "step": "intake", "current_stage": "intake"})
        await update_case_async(case_id, status="PROCESSING", current_stage="intake")
        await record_stage(case_id, "intake", "system", "Case received and queued for processing")

        await send_slack_notification("case-created", {
            "case_id": case_id, "full_name": hire_profile.get("full_name"),
            "destination_country": destination_country, "destination_city": destination_city,
            **hire_profile,
        })

        doc_results = []
        all_docs_ok = True
        needs_renewal = False
        low_conf_docs = []

        for i, file_path in enumerate(file_paths):
            doc_id = str(uuid.uuid4())
            filename = Path(file_path).name
            now = datetime.now(timezone.utc).isoformat()

            await insert_document_async(id=doc_id, case_id=case_id, filename=filename, status="PROCESSING", created_at=now)

            await set_progress(case_id, {
                "status": "PROCESSING", "step": "document_extraction",
                "doc_index": i, "total_docs": len(file_paths), "current_stage": "document_verification",
            })

            try:
                from agents.doc_sentry import run as doc_sentry_run
                doc_data = await asyncio.to_thread(doc_sentry_run, file_path)

                if doc_data.get("error"):
                    doc_status = "FAILED"
                    all_docs_ok = False
                elif doc_data.get("date_errors"):
                    doc_status = "EXPIRED"
                    needs_renewal = True
                    all_docs_ok = False
                elif doc_data.get("date_warnings"):
                    doc_status = "EXPIRING_SOON"
                else:
                    doc_status = "VERIFIED"

                await update_document_async(doc_id,
                    status=doc_status,
                    document_type=doc_data.get("document_type"),
                    extracted_data=json.dumps(doc_data),
                    date_errors=json.dumps(doc_data.get("date_errors", [])),
                    date_warnings=json.dumps(doc_data.get("date_warnings", [])),
                )

                doc_entry = {
                    "id": doc_id, "filename": filename, "status": doc_status,
                    "document_type": doc_data.get("document_type"),
                    "extracted_data": doc_data,
                    "date_errors": doc_data.get("date_errors", []),
                    "date_warnings": doc_data.get("date_warnings", []),
                }
                doc_results.append(doc_entry)

                if doc_status in ("VERIFIED", "EXPIRING_SOON"):
                    await send_slack_notification("document-verified", {
                        "case_id": case_id, "full_name": hire_profile.get("full_name"),
                        "document_type": doc_data.get("document_type", "Unknown"),
                        "status": doc_status,
                    })

            except Exception as e:
                log.error("Document %s failed: %s", filename, e)
                all_docs_ok = False
                await update_document_async(doc_id, status="ERROR", error=str(e))
                doc_results.append({"id": doc_id, "filename": filename, "status": "ERROR", "error": str(e)})

        await record_stage(case_id, "document_verification", "system",
            f"Processed {len(doc_results)} document(s)")

        if needs_renewal:
            await update_case_async(case_id, current_stage="document_renewal", document_data=json.dumps(doc_results))
            await record_stage(case_id, "document_renewal", "system", "Expired documents flagged for renewal")
            expired_types = [d.get("document_type") or d.get("filename", "unknown") for d in doc_results if d.get("status") == "EXPIRED"]
            await send_slack_notification("document-renewal-needed", {
                "case_id": case_id, "full_name": hire_profile.get("full_name"),
                "expired_docs": expired_types,
            })
            await set_progress(case_id, {
                "status": "AWAITING_RENEWAL", "current_stage": "document_renewal",
                "documents": doc_results,
            })
            return

        if not all_docs_ok:
            failed_docs = [d.get("document_type") or d.get("filename", "unknown") for d in doc_results if d.get("status") in ("FAILED", "ERROR")]
            await update_case_async(case_id, current_stage="manual_review", document_data=json.dumps(doc_results))
            await record_stage(case_id, "manual_review", "system", "Documents flagged for human review")
            await send_slack_notification("manual-review-required", {
                "case_id": case_id, "full_name": hire_profile.get("full_name"),
                "affected_docs": failed_docs,
            })
            await set_progress(case_id, {
                "status": "AWAITING_REVIEW", "current_stage": "manual_review",
                "documents": doc_results,
            })
            decided = await _await_hr_decision(case_id)
            if not decided:
                return
            updated_case = await get_case_async(case_id)
            if updated_case and updated_case.get("status") in ("REJECTED", "ERROR", "ESCALATED"):
                return

        await update_case_async(case_id, current_stage="compliance_check")
        await record_stage(case_id, "compliance_check", "system", "Starting compliance verification")

        await set_progress(case_id, {
            "status": "PROCESSING", "step": "compliance_check", "current_stage": "compliance_check",
            "documents": doc_results,
        })

        merged_doc_data = doc_results[0].get("extracted_data", {}) if doc_results else {}
        doc_type = merged_doc_data.get("document_type", "unknown")
        cache_key = f"compliance:{doc_type}:{destination_country}"

        compliance_result = await compliance_cache.get(cache_key)
        if compliance_result is None:
            from agents.compliance_agent import async_run as compliance_async_run
            compliance_result = await compliance_async_run(merged_doc_data, destination_country)
            await compliance_cache.set(cache_key, compliance_result)

        is_pass = compliance_result.get("status") == "PASS"
        score = compliance_result.get("confidence_score", 0)

        if is_pass:
            await record_stage(case_id, "compliance_check", "system", f"Compliance PASSED (score: {score})")
            await send_slack_notification("compliance-pass", {
                "case_id": case_id, "full_name": hire_profile.get("full_name"),
                "confidence_score": score,
                "confidence_label": compliance_result.get("confidence_label", ""),
            })
        else:
            await record_stage(case_id, "compliance_check", "system", f"Compliance FAILED (score: {score})")
            await record_stage(case_id, "compliance_remediation", "system", "Flagged for document remediation")
            await send_slack_notification("compliance-fail", {
                "case_id": case_id, "full_name": hire_profile.get("full_name"),
                "confidence_score": score,
                "confidence_label": compliance_result.get("confidence_label", ""),
                "missing_documents": compliance_result.get("missing_documents", []),
                "recommendation": compliance_result.get("recommendation", ""),
            })
            await update_case_async(case_id, current_stage="compliance_remediation", compliance_result=json.dumps(compliance_result))
            await set_progress(case_id, {
                "status": "AWAITING_REVIEW", "current_stage": "compliance_remediation",
                "documents": doc_results, "compliance_result": compliance_result,
            })
            decided = await _await_hr_decision(case_id)
            if not decided:
                return
            updated_case = await get_case_async(case_id)
            if updated_case and updated_case.get("status") in ("REJECTED", "ERROR", "ESCALATED"):
                return

        await set_progress(case_id, {
            "status": "PROCESSING", "step": "compliance_check",
            "documents": doc_results, "compliance_result": compliance_result,
            "current_stage": "hr_review",
        })

        await update_case_async(case_id, current_stage="hr_review")
        await record_stage(case_id, "hr_review", "system", "Awaiting HR approval")

        await set_progress(case_id, {
            "status": "AWAITING_HR_DECISION", "current_stage": "hr_review",
            "documents": doc_results, "compliance_result": compliance_result,
        })

        decided = await _await_hr_decision(case_id)
        if not decided:
            return

        updated_case = await get_case_async(case_id)
        if not updated_case or updated_case.get("status") == "REJECTED":
            await record_stage(case_id, "hr_review", "hr_manager", "REJECTED")
            await send_slack_notification("hr-rejected", {
                "case_id": case_id, "full_name": hire_profile.get("full_name"),
                "hr_name": "HR Manager",
            })
            return

        await record_stage(case_id, "hr_review", "hr_manager", "APPROVED")
        await send_slack_notification("hr-approved", {
            "case_id": case_id, "full_name": hire_profile.get("full_name"),
            "hr_name": "HR Manager",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        await update_case_async(case_id, current_stage="relocation_planning")
        await record_stage(case_id, "relocation_planning", "system", "Generating relocation guide")

        await set_progress(case_id, {
            "status": "PROCESSING", "step": "relocation_guide", "current_stage": "relocation_planning",
            "documents": doc_results, "compliance_result": compliance_result,
        })

        from agents.relocation_agent import async_run as relocation_async_run
        relocation_guide = await relocation_async_run(hire_profile)

        await update_case_async(
            case_id, status="COMPLETED", current_stage="completed",
            document_data=json.dumps(doc_results),
            compliance_result=json.dumps(compliance_result),
            relocation_guide=relocation_guide,
        )
        await record_stage(case_id, "completed", "system", "Case completed successfully")

        await send_slack_notification("relocation-ready", {
            "case_id": case_id, "full_name": hire_profile.get("full_name"),
            "destination_city": destination_city,
        })

        await set_progress(case_id, {
            "status": "COMPLETED", "current_stage": "completed",
            "documents": doc_results,
            "compliance_result": compliance_result,
            "relocation_guide": relocation_guide,
        })

    except Exception as e:
        log.error("Case %s failed: %s", case_id, e)
        await update_case_async(case_id, status="ERROR", current_stage="error", error=str(e))
        await record_stage(case_id, "error", "system", f"Error: {str(e)}")
        await send_slack_notification("case-error", {
            "case_id": case_id, "full_name": hire_profile.get("full_name"),
            "error_message": str(e),
        })
        await set_progress(case_id, {"status": "ERROR", "current_stage": "error", "error": str(e)})
    finally:
        for fp in file_paths:
            try:
                os.remove(fp)
            except Exception:
                pass
        await cleanup_progress(case_id)


async def run_document_verify_for_maestro(case_id: str, case: dict):
    try:
        docs = await get_case_documents_async(case_id)
        hire_profile = case.get("hire_profile", {})
        full_name = hire_profile.get("full_name", "") if isinstance(hire_profile, dict) else ""
        upload_dir = settings.upload_dir

        doc_results = []
        files_processed = False
        for doc in docs:
            if doc.get("status") in ("VERIFIED", "FAILED", "ERROR", "EXPIRED", "EXPIRING_SOON"):
                doc_results.append({
                    "id": doc["id"],
                    "filename": doc.get("filename"),
                    "status": doc["status"],
                    "document_type": doc.get("document_type"),
                    "extracted_data": doc.get("extracted_data"),
                })
                continue

            from agents.doc_sentry import run as doc_sentry_run

            file_path = None
            for f in os.listdir(upload_dir):
                if f.startswith(case_id):
                    file_path = upload_dir / f
                    break

            if not file_path or not file_path.exists():
                doc_results.append({
                    "id": doc["id"],
                    "filename": doc.get("filename"),
                    "status": "ERROR",
                    "error": "File not found in uploads",
                })
                continue

            doc_data = await asyncio.to_thread(doc_sentry_run, str(file_path))

            if doc_data.get("error"):
                doc_status = "FAILED"
            elif doc_data.get("date_errors"):
                doc_status = "EXPIRED"
            elif doc_data.get("date_warnings"):
                doc_status = "EXPIRING_SOON"
            else:
                doc_status = "VERIFIED"

            await update_document_async(
                doc["id"],
                status=doc_status,
                document_type=doc_data.get("document_type"),
                extracted_data=json.dumps(doc_data),
                date_errors=json.dumps(doc_data.get("date_errors", [])),
                date_warnings=json.dumps(doc_data.get("date_warnings", [])),
            )

            doc_results.append({
                "id": doc["id"],
                "filename": doc.get("filename"),
                "status": doc_status,
                "document_type": doc_data.get("document_type"),
                "extracted_data": doc_data,
            })
            files_processed = True

        if files_processed:
            await update_case_async(case_id, document_data=json.dumps(doc_results))
        await record_stage(case_id, "document_verification", "maestro_webhook", "Completed via Maestro trigger")

        if doc_results:
            await send_slack_notification("document-verified", {
                "case_id": case_id,
                "full_name": full_name,
                "document_type": doc_results[0].get("document_type") or "Document",
                "status": doc_results[0].get("status", "PROCESSING"),
            })
    except Exception as e:
        log.error("Maestro document verify failed for %s: %s", case_id, e)


async def run_compliance_for_maestro(case_id: str, case: dict, hire_profile: dict):
    try:
        fresh_case = await get_case_async(case_id)
        case = fresh_case or case
        document_data = case.get("document_data") or {}
        if isinstance(document_data, list):
            document_data = document_data[0].get("extracted_data", {}) if document_data else {}
        destination_country = case.get("destination_country", "")

        from agents.compliance_agent import async_run as compliance_async_run
        compliance_result = await compliance_async_run(document_data, destination_country)
        await update_case_async(case_id, compliance_result=json.dumps(compliance_result))
        await record_stage(case_id, "compliance_check", "maestro_webhook", "Completed via Maestro trigger")

        full_name = hire_profile.get("full_name", "") if isinstance(hire_profile, dict) else case.get("hire_profile", {})
        if isinstance(full_name, dict):
            full_name = full_name.get("full_name", "")

        is_pass = compliance_result.get("status") == "PASS"
        score = compliance_result.get("confidence_score", 0)
        if is_pass:
            await send_slack_notification("compliance-pass", {
                "case_id": case_id,
                "full_name": full_name,
                "confidence_score": score,
                "confidence_label": compliance_result.get("confidence_label", ""),
            })
        else:
            await send_slack_notification("compliance-fail", {
                "case_id": case_id,
                "full_name": full_name,
                "confidence_score": score,
                "confidence_label": compliance_result.get("confidence_label", ""),
                "missing_documents": compliance_result.get("missing_documents", []),
                "recommendation": compliance_result.get("recommendation", ""),
            })
    except Exception as e:
        log.error("Maestro compliance failed for %s: %s", case_id, e)


async def run_relocation_for_maestro(case_id: str, hire_profile: dict):
    try:
        from agents.relocation_agent import async_run as relocation_async_run
        guide = await relocation_async_run(hire_profile)
        await update_case_async(case_id, relocation_guide=guide)
        await record_stage(case_id, "relocation_planning", "maestro_webhook", "Completed via Maestro trigger")

        full_name = hire_profile.get("full_name", "") if isinstance(hire_profile, dict) else ""
        destination_city = hire_profile.get("destination_city", "") if isinstance(hire_profile, dict) else ""
        await send_slack_notification("relocation-ready", {
            "case_id": case_id,
            "full_name": full_name,
            "destination_city": destination_city,
        })
    except Exception as e:
        log.error("Maestro relocation failed for %s: %s", case_id, e)
