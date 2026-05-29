import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from backend.database import get_case_async, get_case_documents_async, get_case_stages_async, update_case_async, record_stage
from backend.models import MaestroWebhookRequest, HrDecisionRequest
from backend.case_processor import run_compliance_for_maestro, run_relocation_for_maestro, run_document_verify_for_maestro
from backend.utils.sse import set_progress, case_update_events
from backend.slack_notifier import send_slack_notification

router = APIRouter(prefix="/api/webhooks/maestro", tags=["Maestro Webhooks"])


@router.post("/document-verify")
async def maestro_document_verify(request: MaestroWebhookRequest):
    case_id = request.case_id
    case = await get_case_async(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    asyncio.create_task(run_document_verify_for_maestro(case_id, case))
    return {"case_id": case_id, "status": "PROCESSING", "message": "Document verification dispatched"}


@router.post("/compliance-check")
async def maestro_compliance_check(request: MaestroWebhookRequest):
    case_id = request.case_id
    case = await get_case_async(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    hire_profile = request.payload.get("hire_profile", {})
    asyncio.create_task(run_compliance_for_maestro(case_id, case, hire_profile))
    return {"case_id": case_id, "status": "PROCESSING", "message": "Compliance check dispatched"}


@router.post("/relocation-guide")
async def maestro_relocation_guide(request: MaestroWebhookRequest):
    case_id = request.case_id
    case = await get_case_async(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    hire_profile = request.payload.get("hire_profile", case.get("hire_profile", {}))
    asyncio.create_task(run_relocation_for_maestro(case_id, hire_profile))
    return {"case_id": case_id, "status": "PROCESSING", "message": "Relocation guide dispatched"}


@router.post("/hr-decision")
async def maestro_hr_decision(request: HrDecisionRequest):
    case_id = request.case_id
    case = await get_case_async(case_id)
    if not case:
        raise HTTPException(404, "Case not found")

    decision = request.decision.upper()
    if decision not in ("APPROVE", "REJECT"):
        raise HTTPException(400, "Decision must be APPROVE or REJECT")

    if decision == "APPROVE":
        current = case.get("current_stage", "hr_review")
        await update_case_async(case_id, status="PROCESSING", current_stage=current)
        await record_stage(case_id, current, request.reviewer_name,
                          f"Approved via Maestro: {request.comments or ''}", decision="APPROVED")
        await set_progress(case_id, {"status": "PROCESSING", "decision": "APPROVED"})
    else:
        await update_case_async(case_id, status="REJECTED", current_stage="rejected")
        await record_stage(case_id, "rejected", request.reviewer_name,
                          f"Rejected via Maestro: {request.comments or ''}", decision="REJECTED")
        await set_progress(case_id, {"status": "REJECTED", "decision": "REJECTED"})

    event = case_update_events.get(case_id)
    if event:
        event.set()

    case = await get_case_async(case_id)
    hire_profile = case.get("hire_profile", {}) if case else {}
    full_name = hire_profile.get("full_name", "") if isinstance(hire_profile, dict) else ""
    if decision == "APPROVE":
        await send_slack_notification("hr-approved", {
            "case_id": case_id,
            "full_name": full_name,
            "hr_name": request.reviewer_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    else:
        await send_slack_notification("hr-rejected", {
            "case_id": case_id,
            "full_name": full_name,
            "hr_name": request.reviewer_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return {"case_id": case_id, "status": "updated", "decision": decision}


@router.get("/case-status/{case_id}")
async def maestro_case_status(case_id: str):
    case = await get_case_async(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    docs = await get_case_documents_async(case_id)
    stages = await get_case_stages_async(case_id)
    return {
        "case_id": case_id,
        "status": case.get("status"),
        "current_stage": case.get("current_stage"),
        "documents": [
            {"id": d["id"], "filename": d["filename"], "status": d["status"], "document_type": d.get("document_type")}
            for d in docs
        ],
        "stages": [
            {"stage": s["stage"], "entered_at": s["entered_at"], "actor": s["actor"], "decision": s.get("decision")}
            for s in stages
        ],
        "compliance_result": case.get("compliance_result"),
        "relocation_guide": case.get("relocation_guide"),
        "error": case.get("error"),
    }


@router.post("/case-status")
async def maestro_case_status_post(request: MaestroWebhookRequest):
    case = await get_case_async(request.case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    docs = await get_case_documents_async(request.case_id)
    stages = await get_case_stages_async(request.case_id)
    return {
        "case_id": request.case_id,
        "status": case.get("status"),
        "current_stage": case.get("current_stage"),
        "documents": [
            {"id": d["id"], "filename": d["filename"], "status": d["status"], "document_type": d.get("document_type")}
            for d in docs
        ],
        "stages": [
            {"stage": s["stage"], "entered_at": s["entered_at"], "actor": s["actor"], "decision": s.get("decision")}
            for s in stages
        ],
        "compliance_result": case.get("compliance_result"),
        "relocation_guide": case.get("relocation_guide"),
        "error": case.get("error"),
    }
