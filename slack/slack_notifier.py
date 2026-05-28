import os
import json
import hashlib
import hmac
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID")
SLACK_CANDIDATE_CHANNEL_ID = os.getenv("SLACK_CANDIDATE_CHANNEL_ID") or SLACK_CHANNEL_ID
SLACK_MANAGER_ID = os.getenv("MANAGER_SLACK_ID")

client = WebClient(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("slack_notifier")

app = FastAPI(title="GlobalTalent Slack Notifier", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def send_slack_message(channel: str, text: str, blocks: list = None):
    if not client:
        logger.warning("Slack client not configured — skipping message")
        return
    try:
        kwargs = {"channel": channel, "text": text}
        if blocks:
            kwargs["blocks"] = blocks
        response = client.chat_postMessage(**kwargs)
        logger.info(f"Message sent to {channel}: {response['ts']}")
    except SlackApiError as e:
        logger.error(f"Slack API error: {e.response['error']}")


def _make_interactive_blocks(body: str, actions: list, context: str = "") -> list:
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": body}},
    ]
    if context:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": context}]})
    blocks.append({"type": "actions", "elements": actions})
    return blocks


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "slack-notifier",
        "slack_configured": client is not None,
    }


@app.post("/notify/case-created")
async def notify_case_created(payload: dict):
    case_id = payload.get("case_id", "N/A")
    blocks = _make_interactive_blocks(
        f" New Case Created\n*Candidate:* {payload.get('full_name', 'N/A')}\n*Destination:* {payload.get('destination_city', 'N/A')}, {payload.get('destination_country', 'N/A')}\n*Document:* {payload.get('document_type', 'N/A')}",
        [],
        f"Case: `{case_id}` — Processing started"
    )
    await send_slack_message(SLACK_CHANNEL_ID, f"New case created for {payload.get('full_name', 'N/A')}", blocks)
    return {"status": "ok", "endpoint": "case-created"}


@app.post("/notify/compliance-pass")
async def notify_compliance_pass(payload: dict):
    case_id = payload.get("case_id", "N/A")
    blocks = _make_interactive_blocks(
        f" Compliance Check PASSED\n*Candidate:* {payload.get('full_name', 'N/A')}\n*Score:* {payload.get('confidence_score', 'N/A')}/100 — {payload.get('confidence_label', 'N/A')}",
        [
            {"type": "button", "text": {"type": "plain_text", "text": "Approve Case"}, "style": "primary", "value": f"hr-approve:{case_id}"},
            {"type": "button", "text": {"type": "plain_text", "text": "Reject Case"}, "style": "danger", "value": f"hr-reject:{case_id}"},
        ],
        f"Case: `{case_id}` — Action required"
    )
    await send_slack_message(SLACK_CHANNEL_ID, f"Compliance passed for {payload.get('full_name', 'N/A')}", blocks)
    return {"status": "ok", "endpoint": "compliance-pass"}


@app.post("/notify/compliance-fail")
async def notify_compliance_fail(payload: dict):
    case_id = payload.get("case_id", "N/A")
    missing = payload.get("missing_documents", [])
    missing_text = ", ".join(missing) if missing else "None"
    blocks = _make_interactive_blocks(
        f" Compliance Check FAILED\n*Candidate:* {payload.get('full_name', 'N/A')}\n*Score:* {payload.get('confidence_score', 'N/A')}/100\n*Missing:* {missing_text}\n*Recommendation:* {payload.get('recommendation', 'N/A')}",
        [
            {"type": "button", "text": {"type": "plain_text", "text": "Request Documents"}, "style": "primary", "value": f"request-docs:{case_id}"},
            {"type": "button", "text": {"type": "plain_text", "text": "Escalate"}, "style": "danger", "value": f"escalate:{case_id}"},
        ],
        f"Case: `{case_id}` — Action required"
    )
    await send_slack_message(SLACK_CHANNEL_ID, f"Compliance failed for {payload.get('full_name', 'N/A')}", blocks)
    return {"status": "ok", "endpoint": "compliance-fail"}


@app.post("/notify/hr-approved")
async def notify_hr_approved(payload: dict):
    full_name = payload.get("full_name", "N/A")
    case_id = payload.get("case_id", "N/A")
    hr_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f" Case Approved by HR\n*Candidate:* {full_name}\n*Approved by:* {payload.get('hr_name', 'N/A')}\n*Time:* {payload.get('timestamp', 'N/A')}"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Generating relocation guide..."}]},
    ]
    await send_slack_message(SLACK_CHANNEL_ID, f"Case approved for {full_name}", hr_blocks)
    if SLACK_CANDIDATE_CHANNEL_ID:
        candidate_msg = f" Great news {full_name}! Your documents have been approved! Your personalized relocation guide is being prepared now."
        await send_slack_message(SLACK_CANDIDATE_CHANNEL_ID, candidate_msg)
    return {"status": "ok", "endpoint": "hr-approved"}


@app.post("/notify/hr-rejected")
async def notify_hr_rejected(payload: dict):
    full_name = payload.get("full_name", "N/A")
    case_id = payload.get("case_id", "N/A")
    hr_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f" Case Rejected by HR\n*Candidate:* {full_name}\n*Rejected by:* {payload.get('hr_name', 'N/A')}\n*Time:* {payload.get('timestamp', 'N/A')}"}},
    ]
    await send_slack_message(SLACK_CHANNEL_ID, f"Case rejected for {full_name}", hr_blocks)
    if SLACK_CANDIDATE_CHANNEL_ID:
        candidate_msg = f"Hi {full_name}, your documents need attention. Please resubmit the required documents. Our HR team will guide you."
        await send_slack_message(SLACK_CANDIDATE_CHANNEL_ID, candidate_msg)
    return {"status": "ok", "endpoint": "hr-rejected"}


@app.post("/notify/relocation-ready")
async def notify_relocation_ready(payload: dict):
    full_name = payload.get("full_name", "N/A")
    case_id = payload.get("case_id", "N/A")
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"Relocation Guide Ready — {full_name}"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"Welcome to *{payload.get('destination_city', 'N/A')}!* Your guide is ready with neighbourhoods, schools, cost estimates, and a 30-day checklist."}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Case `{case_id}` — All stages complete"}]},
    ]
    channel = SLACK_CANDIDATE_CHANNEL_ID or SLACK_CHANNEL_ID
    await send_slack_message(channel, f"Relocation guide ready for {full_name}", blocks)
    return {"status": "ok", "endpoint": "relocation-ready"}


@app.post("/notify/case-error")
async def notify_case_error(payload: dict):
    case_id = payload.get("case_id", "N/A")
    blocks = _make_interactive_blocks(
        f" Case Error Detected\n*Candidate:* {payload.get('full_name', 'N/A')}\n*Error:* {payload.get('error_message', 'N/A')}",
        [
            {"type": "button", "text": {"type": "plain_text", "text": "Investigate"}, "style": "danger", "value": f"investigate:{case_id}"},
        ],
        f"Case: `{case_id}` — Manual intervention needed"
    )
    await send_slack_message(SLACK_CHANNEL_ID, f"Error in case {case_id}", blocks)
    return {"status": "ok", "endpoint": "case-error"}


@app.post("/notify/manual-review-required")
async def notify_manual_review(payload: dict):
    case_id = payload.get("case_id", "N/A")
    affected_docs = payload.get("affected_docs", [])
    doc_text = ", ".join(affected_docs) if affected_docs else "Unknown"
    blocks = _make_interactive_blocks(
        f" Manual Review Required\n*Candidate:* {payload.get('full_name', 'N/A')}\n*Documents needing review:* {doc_text}\nPlease verify the extracted data.",
        [
            {"type": "button", "text": {"type": "plain_text", "text": "Approve"}, "style": "primary", "value": f"approve:{case_id}"},
            {"type": "button", "text": {"type": "plain_text", "text": "Reject"}, "style": "danger", "value": f"reject:{case_id}"},
            {"type": "button", "text": {"type": "plain_text", "text": "Request Info"}, "value": f"request-info:{case_id}"},
        ],
        f"Case: `{case_id}` — Action required"
    )
    await send_slack_message(SLACK_CHANNEL_ID, f"Manual review required for {payload.get('full_name', 'N/A')}", blocks)
    return {"status": "ok", "endpoint": "manual-review-required"}


@app.post("/notify/document-renewal-needed")
async def notify_document_renewal(payload: dict):
    case_id = payload.get("case_id", "N/A")
    expired_docs = payload.get("expired_docs", [])
    doc_text = ", ".join(expired_docs) if expired_docs else "Unknown"
    blocks = _make_interactive_blocks(
        f" Document Renewal Needed\n*Candidate:* {payload.get('full_name', 'N/A')}\n*Expired documents:* {doc_text}\nPlease contact the candidate for renewed documents.",
        [
            {"type": "button", "text": {"type": "plain_text", "text": "Contact Candidate"}, "style": "primary", "value": f"contact:{case_id}"},
            {"type": "button", "text": {"type": "plain_text", "text": "Put on Hold"}, "value": f"hold:{case_id}"},
        ],
        f"Case: `{case_id}`"
    )
    await send_slack_message(SLACK_CHANNEL_ID, f"Expired documents for {payload.get('full_name', 'N/A')}", blocks)
    return {"status": "ok", "endpoint": "document-renewal-needed"}


@app.get("/notify/interactive")
async def slack_interactive_get(request: Request):
    return JSONResponse(content={"text": "This endpoint requires POST with Slack payload"})


@app.post("/notify/interactive")
async def slack_interactive(request: Request):
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if SLACK_SIGNING_SECRET:
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        my_sig = "v0=" + hmac.new(
            SLACK_SIGNING_SECRET.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(my_sig, signature):
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
    action_map = {
        "hr-approve": f"Case {case_id[:8]} approved. Proceeding with relocation.",
        "hr-reject": f"Case {case_id[:8]} rejected.",
        "approve": "Documents approved. Continuing with compliance check.",
        "reject": "Case rejected.",
        "request-info": "Info request sent to candidate.",
        "request-docs": "Document request sent to candidate.",
        "escalate": f"Case escalated to manager.",
        "contact": "Candidate contact initiated.",
        "hold": f"Case {case_id[:8]} put on hold.",
        "investigate": f"Case {case_id[:8]} flagged for investigation.",
    }

    response_text = action_map.get(action_type, f"Action '{action_type}' received for case {case_id[:8]}.")

    if action_type == "escalate" and SLACK_MANAGER_ID and client:
        try:
            client.chat_postMessage(
                channel=SLACK_MANAGER_ID,
                text=f"Case {case_id[:8]} has been escalated by {user_name}. Immediate attention required."
            )
        except SlackApiError as e:
            logger.error(f"Failed to notify manager: {e.response['error']}")

    logger.info("Slack interactive: %s by %s for case %s", action_type, user_name, case_id)
    return JSONResponse(content={"text": response_text})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
