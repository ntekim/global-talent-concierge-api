import json
import hashlib
import hmac
import logging

from backend.config import settings

log = logging.getLogger("server")

SLACK_AVAILABLE = False
WebClient = None
SlackApiError = Exception
try:
    from slack_sdk import WebClient as SlackWebClient
    from slack_sdk.errors import SlackApiError as SlackError
    WebClient = SlackWebClient
    SlackApiError = SlackError
    SLACK_AVAILABLE = True
except ImportError:
    pass

_slack_client = None


def get_slack_client():
    global _slack_client
    if _slack_client is None and SLACK_AVAILABLE and settings.slack_bot_token:
        _slack_client = WebClient(token=settings.slack_bot_token)
    return _slack_client


def verify_slack_signature(body: bytes, timestamp: str, signature: str) -> bool:
    if not settings.slack_signing_secret:
        return True
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    my_sig = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(my_sig, signature)


def _build_blocks(notification_type: str, payload: dict) -> tuple[list, str]:
    full_name = payload.get("full_name", "Candidate")
    case_id = payload.get("case_id", "N/A")
    blocks = []
    text = ""

    if notification_type == "case-created":
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "New Relocation Case Created"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Candidate:* {full_name}"},
                {"type": "mrkdwn", "text": f"*Destination:* {payload.get('destination_city', 'N/A')}, {payload.get('destination_country', 'N/A')}"},
                {"type": "mrkdwn", "text": f"*Case ID:* `{case_id}`"},
            ]},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": "Processing started..."}]},
        ]
        text = f"New case created for {full_name}"

    elif notification_type == "document-verified":
        prefix = "[PASS]" if payload.get("status") == "VERIFIED" else "[WARN]"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"{prefix} Document: *{payload.get('document_type', 'Unknown')}*"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Status:* {payload.get('status', 'N/A')}"},
            ]},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Case: `{case_id}` - {full_name}"}]},
        ]
        text = f"Document {payload.get('document_type', 'Unknown')}: {payload.get('status', 'N/A')}"

    elif notification_type == "manual-review-required":
        doc_types = ", ".join(payload.get("affected_docs", ["Unknown"]))
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Manual Review Required"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Document verification needs human review for *{full_name}*."}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Case ID:* `{case_id}`"},
                {"type": "mrkdwn", "text": f"*Documents:* {doc_types}"},
            ]},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Approve"}, "style": "primary", "value": f"approve:{case_id}"},
                {"type": "button", "text": {"type": "plain_text", "text": "Reject"}, "style": "danger", "value": f"reject:{case_id}"},
                {"type": "button", "text": {"type": "plain_text", "text": "Request Info"}, "value": f"request-info:{case_id}"},
            ]},
        ]
        text = f"Manual review required for {full_name}"

    elif notification_type == "document-renewal-needed":
        expired = ", ".join(payload.get("expired_docs", ["Unknown"]))
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Document Renewal Needed"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*{full_name}* has expired documents requiring renewal."}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Case ID:* `{case_id}`"},
                {"type": "mrkdwn", "text": f"*Expired:* {expired}"},
            ]},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Contact Candidate"}, "style": "primary", "value": f"contact:{case_id}"},
                {"type": "button", "text": {"type": "plain_text", "text": "Put on Hold"}, "value": f"hold:{case_id}"},
            ]},
        ]
        text = f"Expired documents for {full_name}"

    elif notification_type == "compliance-pass":
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Compliance Check PASSED - *{full_name}*"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Score:* {payload.get('confidence_score', 'N/A')}/100"},
                {"type": "mrkdwn", "text": f"*Label:* {payload.get('confidence_label', 'N/A')}"},
            ]},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Approve Case"}, "style": "primary", "value": f"hr-approve:{case_id}"},
                {"type": "button", "text": {"type": "plain_text", "text": "Reject Case"}, "style": "danger", "value": f"hr-reject:{case_id}"},
            ]},
        ]
        text = f"Compliance passed for {full_name}"

    elif notification_type == "compliance-fail":
        missing = ", ".join(payload.get("missing_documents", [])) or "None"
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Compliance Check FAILED - *{full_name}*"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Score:* {payload.get('confidence_score', 'N/A')}/100"},
                {"type": "mrkdwn", "text": f"*Missing:* {missing}"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Recommendation:* {payload.get('recommendation', 'N/A')}"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Request Documents"}, "style": "primary", "value": f"request-docs:{case_id}"},
                {"type": "button", "text": {"type": "plain_text", "text": "Escalate"}, "style": "danger", "value": f"escalate:{case_id}"},
            ]},
        ]
        text = f"Compliance failed for {full_name}"

    elif notification_type == "hr-approved":
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Case Approved by HR - *{full_name}*"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Approved by:* {payload.get('hr_name', 'HR Manager')}"},
                {"type": "mrkdwn", "text": f"*Time:* {payload.get('timestamp', 'N/A')}"},
            ]},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": "Generating relocation guide..."}]},
        ]
        text = f"Case approved for {full_name}"

    elif notification_type == "hr-rejected":
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Case Rejected by HR - *{full_name}*"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Rejected by:* {payload.get('hr_name', 'HR Manager')}"},
            ]},
        ]
        text = f"Case rejected for {full_name}"

    elif notification_type == "relocation-ready":
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": f"Relocation Guide Ready - {full_name}"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"Welcome to *{payload.get('destination_city', 'N/A')}!* Guide is ready."}},
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Case `{case_id}` - All stages complete"}]},
        ]
        text = f"Relocation guide ready for {full_name}"

    elif notification_type == "case-error":
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Case Error"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Candidate:* {full_name}"},
                {"type": "mrkdwn", "text": f"*Case ID:* `{case_id}`"},
            ]},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Error:* {payload.get('error_message', 'Unknown')}"}},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Investigate"}, "style": "danger", "value": f"investigate:{case_id}"},
            ]},
        ]
        text = f"Error in case {case_id}"

    return blocks, text


async def send_slack_notification(notification_type: str, payload: dict):
    client = get_slack_client()
    if not client:
        return

    channel = payload.get("channel", settings.slack_channel_id)
    blocks, text = _build_blocks(notification_type, payload)

    try:
        if blocks:
            client.chat_postMessage(channel=channel, text=text, blocks=blocks)
        else:
            client.chat_postMessage(channel=channel, text=text)
        log.info("Slack sent: %s for case %s", notification_type, payload.get("case_id", "N/A"))
    except SlackApiError as e:
        log.error("Slack error for %s: %s", notification_type, e.response.get("error", str(e)))

    if notification_type == "hr-approved" and settings.slack_candidate_channel_id:
        try:
            client.chat_postMessage(
                channel=settings.slack_candidate_channel_id,
                text=f"Great news {payload.get('full_name', 'Candidate')}! Your documents have been approved. Your relocation guide is being prepared."
            )
        except SlackApiError:
            pass


async def send_slack_ephemeral(channel: str, user: str, text: str):
    client = get_slack_client()
    if not client:
        return
    try:
        client.chat_postEphemeral(channel=channel, user=user, text=text)
    except SlackApiError:
        pass


async def notify_manager_slack(case_id: str, message: str):
    if not settings.slack_manager_id:
        return
    client = get_slack_client()
    if not client:
        return
    try:
        client.chat_postMessage(channel=settings.slack_manager_id, text=message)
    except SlackApiError:
        pass
