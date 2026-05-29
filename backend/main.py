import asyncio
import time
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.database import db_pool, init_db
from backend.services.cache import compliance_cache
from backend.services.rate_limiter import rate_limiter
from backend.services.task_manager import task_manager
from backend.routers import cases, webhooks, slack, system
from logger import get_logger

log = get_logger("server")


async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    allowed = await rate_limiter.check(client_ip)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded. Try again later.", "retry_after": 60},
            headers={"Retry-After": "60"},
        )
    return await call_next(request)


async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = req_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


async def timing_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    req_id = getattr(request.state, "request_id", "none")[:8]
    log.info("[%s] %s %s - %dms", req_id, request.method, request.url.path, elapsed_ms)
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    return response


async def housekeeper():
    while True:
        await asyncio.sleep(settings.housekeeper_interval)
        try:
            swept_cache = await compliance_cache.sweep()
            swept_rate = await rate_limiter.sweep()
            log.info("Housekeeper: swept %d cache entries, %d rate-limit entries", swept_cache, swept_rate)
        except Exception as e:
            log.warning("Housekeeper error: %s", e)


async def lifespan(app: FastAPI):
    log.info("Starting database pool...")
    await db_pool.start()
    log.info("Initializing database...")
    await init_db()
    log.info("Starting housekeeper...")
    hk_task = asyncio.create_task(housekeeper(), name="housekeeper")
    log.info("Server started")
    yield
    log.info("Shutting down: cancelling pending cases...")
    await task_manager.cancel_all()
    log.info("Shutting down: stopping housekeeper...")
    hk_task.cancel()
    try:
        await hk_task
    except asyncio.CancelledError:
        pass
    log.info("Shutting down: closing database pool...")
    await db_pool.stop()
    log.info("Server shut down")


app = FastAPI(
    title="GlobalTalent AI Agent API",
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=500)
app.middleware("http")(request_id_middleware)
app.middleware("http")(timing_middleware)
app.middleware("http")(rate_limit_middleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def global_error_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "none")[:8]
    log.error("[%s] Unhandled error on %s %s: %s", req_id, request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "request_id": req_id},
    )

app.include_router(system.router)
app.include_router(cases.router)
app.include_router(webhooks.router)
app.include_router(slack.router)
