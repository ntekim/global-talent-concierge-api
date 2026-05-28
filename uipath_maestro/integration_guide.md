# UiPath Maestro Case Integration Guide

## Overview

This guide explains how to deploy the GlobalTalent Relocation solution on UiPath Automation Cloud using Maestro Case Management (Track 1).

## Prerequisites

- UiPath Automation Cloud tenant with Maestro enabled
- Access to UiPath Labs (request via [this form](https://bit.ly/agenthack26form))
- Your Python backend server deployed and reachable from UiPath Cloud

## Step 1: Deploy the Python Backend

The Python server must be publicly accessible so Maestro can call its webhooks.

### Option A: Cloud deployment (recommended)

```bash
# Deploy to Railway / Render / Fly.io / Azure App Service
# Set environment variables:
GT_DB_PATH=/app/cases.db
GT_UPLOAD_DIR=/app/uploads
GT_SLACK_BOT_TOKEN=xoxb-...
GT_SLACK_SIGNING_SECRET=...
GT_SLACK_CHANNEL_ID=C...
GT_SLACK_CANDIDATE_CHANNEL_ID=C...
GT_SLACK_MANAGER_ID=U...
GT_MAESTRO_WEBHOOK_SECRET=your-secret
```

### Option B: ngrok for development

```bash
ngrok http 8000
# Use the ngrok URL (e.g., https://abc123.ngrok.io) as your base URL
```

## Step 2: Create the Maestro Case

1. Log in to UiPath Automation Cloud
2. Go to **Maestro** > **Case Management**
3. Click **Create Case Definition**
4. Import the `maestro_case_definition.json` file
5. Map the webhook URLs to your deployed server URL:
   - Replace `https://<your-server>` with your actual server URL
6. Publish the case definition

## Step 3: Configure Slack Integration

1. Create a Slack App at https://api.slack.com/apps
2. Add Bot Token with `chat:write`, `chat:write.public`, `commands` scopes
3. Enable **Interactivity** and set the Request URL to:
   `https://<your-server>/api/slack/interactive`
4. Install the app to your workspace
5. Set environment variables on your server:
   ```
   GT_SLACK_BOT_TOKEN=xoxb-...
   GT_SLACK_SIGNING_SECRET=...
   GT_SLACK_CHANNEL_ID=CHRTEAM
   GT_SLACK_CANDIDATE_CHANNEL_ID=CCANDIDATES
   GT_SLACK_MANAGER_ID=UHRMANAGER
   ```

## Step 4: Test End-to-End Flow

1. **Start the server**: `uvicorn server:app --port 8000`
2. **Create a case** via API or frontend:
   ```
   POST /api/cases
   Files: test_passport.png, test_visa.pdf
   destination_country: Germany
   destination_city: Berlin
   full_name: John Doe
   ```
3. **Watch the Maestro Case Board** as the case moves through stages
4. **Check Slack** for interactive notifications at each stage
5. **Click Approve** on the HR Review notification in Slack

## Case Stages Flow

```
Intake → Document Verification → Compliance Check → HR Review → Relocation Planning → Completed
                                    ↓                      ↓
                            Document Renewal         Compliance Remediation
                                    ↓                      ↓
                            Manual Review            Escalated / Rejected
```

## Webhook Reference

| Endpoint | Method | Called By | Purpose |
|---|---|---|---|
| `/api/webhooks/maestro/document-verify` | POST | Maestro | Trigger DocSentry agent |
| `/api/webhooks/maestro/compliance-check` | POST | Maestro | Trigger ComplianceAgent |
| `/api/webhooks/maestro/relocation-guide` | POST | Maestro | Trigger RelocationAgent |
| `/api/webhooks/maestro/hr-decision` | POST | Maestro | Submit HR approve/reject |
| `/api/webhooks/maestro/case-status/{case_id}` | GET | Maestro | Poll case status |
| `/api/slack/interactive` | POST | Slack | Handle button clicks |
| `/api/cases/{case_id}/timeline` | GET | Dashboard | Get full case timeline |
