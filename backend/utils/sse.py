import asyncio
import json
from typing import AsyncGenerator

from backend.config import settings
from backend.database import get_case_async

case_progress: dict[str, dict] = {}
case_update_events: dict[str, asyncio.Event] = {}
_progress_lock = asyncio.Lock()


async def set_progress(case_id: str, data: dict):
    async with _progress_lock:
        case_progress[case_id] = data
        event = case_update_events.get(case_id)
    if event:
        event.set()


async def get_progress(case_id: str) -> dict:
    async with _progress_lock:
        return case_progress.get(case_id, {"status": "PENDING"})


async def cleanup_progress(case_id: str):
    async with _progress_lock:
        case_progress.pop(case_id, None)
        case_update_events.pop(case_id, None)


async def sse_generator(case_id: str) -> AsyncGenerator[str, None]:
    last_data = ""
    try:
        while True:
            progress = await get_progress(case_id)
            status = progress.get("status")

            if status == "PENDING" and not case_update_events.get(case_id):
                case = await get_case_async(case_id)
                if case and case.get("status") in ("COMPLETED", "ERROR"):
                    progress = {
                        "status": case["status"],
                        "document_data": case.get("document_data"),
                        "compliance_result": case.get("compliance_result"),
                        "relocation_guide": case.get("relocation_guide"),
                        "error": case.get("error"),
                    }
                    yield f"data: {json.dumps(progress, default=str)}\n\n"
                    break

            current = json.dumps(progress, default=str)
            if current != last_data:
                yield f"data: {current}\n\n"
                last_data = current
            if status in ("COMPLETED", "ERROR", "REJECTED"):
                break

            event = case_update_events.get(case_id)
            if event:
                event.clear()
                try:
                    await asyncio.wait_for(event.wait(), timeout=settings.sse_heartbeat)
                except asyncio.TimeoutError:
                    yield f": heartbeat\n\n"
            else:
                await asyncio.sleep(2.0)
                yield f": heartbeat\n\n"
    except asyncio.CancelledError:
        pass


async def register_case(case_id: str):
    case_update_events[case_id] = asyncio.Event()
