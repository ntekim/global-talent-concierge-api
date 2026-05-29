import asyncio

from fastapi import APIRouter

from backend.database import db_pool, get_case_async
from backend.services.cache import compliance_cache
from backend.services.rate_limiter import rate_limiter
from backend.services.task_manager import task_manager
from backend.slack_notifier import get_slack_client

router = APIRouter(tags=["System"])


@router.get("/health")
async def health():
    try:
        async with db_pool.connect() as conn:
            def _ping(c):
                c.execute("SELECT 1").fetchone()
            await asyncio.to_thread(_ping, conn)
        return {
            "status": "ok",
            "database": "connected",
            "cache_size": await compliance_cache.size(),
            "active_cases": task_manager.active_count,
            "slack_configured": get_slack_client() is not None,
            "version": "3.0.0",
        }
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "error", "database": str(e)})


@router.get("/api/cache/stats")
async def cache_stats():
    return {
        "compliance_cache_size": await compliance_cache.size(),
        "active_cases": task_manager.active_count,
        "rate_limit_entries": len(rate_limiter._store),
    }
