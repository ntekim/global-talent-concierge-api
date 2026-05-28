import asyncio
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.database import (
    insert_case_async, get_case_async, get_case_documents_async,
    get_case_stages_async, list_cases_async,
)
from backend.models import CaseResponse, CaseListResponse, HrDecisionRequest
from backend.case_processor import process_case
from backend.utils.sse import sse_generator, register_case
from backend.services.task_manager import task_manager

router = APIRouter(prefix="/api", tags=["Cases"])


@router.post("/cases", response_model=dict)
async def create_case(
    files: List[UploadFile] = File(...),
    destination_country: str = Form(...),
    destination_city: str = Form(...),
    full_name: str = Form("Unknown"),
    family_size: int = Form(1),
    monthly_budget_usd: float = Form(0.0),
):
    if not files or len(files) == 0:
        raise HTTPException(400, "At least one file is required")

    for f in files:
        if not f.filename:
            raise HTTPException(400, "All files must have a filename")

    case_id = str(uuid.uuid4())
    hire_profile = {
        "full_name": full_name,
        "family_size": family_size,
        "monthly_budget_usd": monthly_budget_usd,
        "destination_city": destination_city,
    }

    now = datetime.now(timezone.utc).isoformat()
    await insert_case_async(
        id=case_id, status="PENDING", created_at=now, updated_at=now,
        destination_country=destination_country, destination_city=destination_city,
        hire_profile=json.dumps(hire_profile),
        current_stage="intake",
    )

    file_paths = []
    max_bytes = settings.max_upload_mb * 1024 * 1024

    for file in files:
        safe_name = hashlib.sha256(file.filename.encode()).hexdigest()[:12]
        ext = Path(file.filename).suffix
        file_path = settings.upload_dir / f"{case_id}_{safe_name}{ext}"
        content = await file.read()
        if len(content) > max_bytes:
            for fp in file_paths:
                try: os.remove(fp)
                except: pass
            raise HTTPException(413, f"File too large. Max {settings.max_upload_mb}MB per file.")

        def _save(path, data):
            with open(path, "wb") as f:
                f.write(data)
        await asyncio.to_thread(_save, file_path, content)
        file_paths.append(str(file_path))

    await register_case(case_id)

    asyncio.create_task(task_manager.run(
        case_id,
        process_case(case_id, file_paths, destination_country, destination_city, hire_profile)
    ))

    return {"case_id": case_id, "status": "PENDING", "file_count": len(file_paths)}


@router.get("/cases/{case_id}", response_model=CaseResponse)
async def read_case(case_id: str, stream: bool = False):
    case = await get_case_async(case_id)
    if case is None:
        raise HTTPException(404, "Case not found")

    docs = await get_case_documents_async(case_id)
    stages = await get_case_stages_async(case_id)

    case["documents"] = docs
    case["stages"] = stages

    if stream:
        return StreamingResponse(
            sse_generator(case_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return case


@router.get("/cases", response_model=list[CaseListResponse])
async def list_cases():
    return await list_cases_async()


@router.get("/cases/{case_id}/timeline")
async def get_case_timeline(case_id: str):
    case = await get_case_async(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    stages = await get_case_stages_async(case_id)
    docs = await get_case_documents_async(case_id)
    return {
        "case_id": case_id,
        "status": case.get("status"),
        "current_stage": case.get("current_stage"),
        "stages": [
            {
                "stage": s["stage"],
                "entered_at": s["entered_at"],
                "actor": s["actor"],
                "decision": s.get("decision"),
                "details": s.get("details"),
            }
            for s in stages
        ],
        "documents": [
            {
                "id": d["id"],
                "filename": d["filename"],
                "status": d["status"],
                "document_type": d.get("document_type"),
            }
            for d in docs
        ],
    }
