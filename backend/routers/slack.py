import json

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.database import update_case_async, record_stage, get_case_async
from backend.slack_notifier import get_slack_client, verify_slack_signature
from backend.utils.sse import case_update_events

router = APIRouter(prefix="/api/slack", tags=["Slack"])


@router.post("/interactive")
async def slack_interactive(request: Request):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not verify_slack_signature(body, timestamp, signature):
        raise HTTPException(400, "Invalid Slack signature")

    form_data = await request.form()
    payload_str = form_data.get("payload")
    if not payload_str:
        raise HTTPException(400, "No payload received")

    payload = json.loads(payload_str)
    action = payload.get("actions", [{}])[0].get("value", "")
    user_name = payload.get("user", {}).get("name", "Unknown")

    parts = action.split(":", 1)
    if len(parts) != 2:
        return JSONResponse(content={"text": "Invalid action format"})

    action_type, case_id = parts

    if action_type == "hr-approve":
        await update_case_async(case_id, status="PROCESSING")
        current = (await get_case_async(case_id) or {}).get("current_stage", "hr_review")
        await record_stage(case_id, current, user_name, "Approved via Slack", decision="APPROVED")
        event = case_update_events.get(case_id)
        if event:
            event.set()
        return JSONResponse(content={"text": f"Case {case_id[:8]} approved! Proceeding with relocation guide."})

    elif action_type == "hr-reject":
        await update_case_async(case_id, status="REJECTED", current_stage="rejected")
        await record_stage(case_id, "rejected", user_name, "Rejected via Slack", decision="REJECTED")
        event = case_update_events.get(case_id)
        if event:
            event.set()
        return JSONResponse(content={"text": f"Case {case_id[:8]} has been rejected."})

    elif action_type == "approve":
        await update_case_async(case_id, status="PROCESSING")
        await record_stage(case_id, "manual_review", user_name, "Approved via Slack", decision="APPROVED")
        event = case_update_events.get(case_id)
        if event:
            event.set()
        return JSONResponse(content={"text": "Documents approved. Continuing with compliance check."})

    elif action_type == "reject":
        await update_case_async(case_id, status="REJECTED", current_stage="rejected")
        await record_stage(case_id, "rejected", user_name, "Rejected via Slack", decision="REJECTED")
        event = case_update_events.get(case_id)
        if event:
            event.set()
        return JSONResponse(content={"text": "Case rejected."})

    elif action_type == "request-info":
        await record_stage(case_id, "info_requested", user_name, "Additional info requested via Slack", decision="INFO_REQUESTED")
        return JSONResponse(content={"text": "Info request has been sent to the candidate."})

    elif action_type == "escalate":
        await update_case_async(case_id, current_stage="escalated")
        await record_stage(case_id, "escalated", user_name, "Escalated via Slack", decision="ESCALATED")
        if settings.slack_manager_id:
            client = get_slack_client()
            if client:
                try:
                    from slack_sdk.errors import SlackApiError
                    client.chat_postMessage(
                        channel=settings.slack_manager_id,
                        text=f"Case {case_id[:8]} has been escalated by {user_name}. Immediate attention required."
                    )
                except SlackApiError:
                    pass
        return JSONResponse(content={"text": f"Case escalated to manager."})

    return JSONResponse(content={"text": "Action received"})
