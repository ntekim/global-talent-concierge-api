# GlobalTalent Slack Notifier

Standalone Slack notification service for the GlobalTalent project.

## Setup

```bash
cd slack
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your Slack credentials.

## Run

Start the FastAPI server on port 8001:

```bash
python slack_notifier.py
```

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/notify/case-created` | New case created |
| POST | `/notify/compliance-pass` | Compliance check passed |
| POST | `/notify/compliance-fail` | Compliance check failed |
| POST | `/notify/hr-approved` | HR approved the case |
| POST | `/notify/hr-rejected` | HR rejected the case |
| POST | `/notify/relocation-ready` | Relocation guide ready |
| POST | `/notify/case-error` | Case error detected |

## Test

With the server running, execute:

```bash
python test_slack.py
```

## Integration

The GlobalTalent backend (port 8000) calls these endpoints via HTTP:

```python
import httpx
resp = httpx.post("http://localhost:8001/notify/case-created", json={...})
```
