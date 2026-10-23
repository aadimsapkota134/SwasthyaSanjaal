from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.db import TABLES, init_db, session
from backend.routers import auth as auth_router
from backend.routers import eval as eval_router
from backend.routers import intake as intake_router
from backend.routers import patients as patients_router
from backend.seed import seed_all

PROBE_TIMEOUT_SECONDS = 2.0


def _probe_db() -> dict[str, str]:
    """Check database tables and integrity."""
    try:
        with session() as con:
            present = {
                row["name"]
                for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
    except Exception as exc:  # noqa: BLE001
        return {"service": "db", "status": "down", "detail": type(exc).__name__}

    missing = sorted(set(TABLES) - present)
    if missing:
        return {"service": "db", "status": "degraded", "detail": f"missing tables: {', '.join(missing)}"}
    return {"service": "db", "status": "up"}


async def _probe_remote(client: httpx.AsyncClient, name: str, url: str, **kwargs) -> dict[str, str]:
    try:
        response = await client.get(url, timeout=PROBE_TIMEOUT_SECONDS, **kwargs)
    except Exception as exc:  # noqa: BLE001
        return {"service": name, "status": "down", "detail": type(exc).__name__}
    if response.status_code >= 500:
        return {"service": name, "status": "degraded", "detail": f"HTTP {response.status_code}"}
    return {"service": name, "status": "up"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    with session() as con:
        seed_all(con)
    try:
        from backend.nlp.lexicon import reset_lexicon_cache
        reset_lexicon_cache()
    except Exception:
        pass
    yield


app = FastAPI(
    title="SwasthyaSanjaal API",
    description="SwasthyaSanjaal (स्वास्थ्य सञ्जाल) - Nepali Clinical Language Layer & Digital Health Record Engine",
    version="0.1.0",
    lifespan=lifespan,
)

# Reject oversized request bodies from the Content-Length header before the
# multipart/JSON parser buffers them. Slack covers multipart framing overhead
# so a file exactly at the limit is still accepted. Registered BEFORE
# CORSMiddleware so CORS stays outermost and decorates this 413 response.
REQUEST_BODY_LIMIT_BYTES = intake_router.MAX_UPLOAD_BYTES + 1024 * 1024


@app.middleware("http")
async def reject_oversized_request_body(request, call_next):
    content_length = request.headers.get("content-length")
    if content_length is not None and content_length.isdigit():
        if int(content_length) > REQUEST_BODY_LIMIT_BYTES:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": (
                        f"Request body exceeds "
                        f"{REQUEST_BODY_LIMIT_BYTES // (1024 * 1024)} MB limit."
                    )
                },
            )
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api/v1")


@api.get("/health")
async def health() -> dict[str, object]:
    model_probe_url = f"{settings.model_base_url}/api/tags"
    local_probe_url = f"{settings.ollama_url.rstrip('/')}/api/tags"
    async with httpx.AsyncClient() as client:
        remote = await asyncio.gather(
            _probe_remote(
                client,
                "primary_model",
                model_probe_url,
                headers=settings.model_headers,
            ),
            _probe_remote(
                client,
                "fallback_model",
                local_probe_url,
            ),
        )

    db_status = _probe_db()
    services = [db_status, *remote]

    overall_status = "ok" if db_status["status"] in {"up", "pending_init"} else "degraded"

    return {
        "status": overall_status,
        "service": "swasthyasanjaal-api",
        "model_backend": settings.resolved_backend,
        "model": settings.active_model_name,
        "fallback_model": settings.fallback_model_name,
        "services": services,
    }


app.include_router(api)
app.include_router(intake_router.router, prefix="/api/v1")
app.include_router(patients_router.router, prefix="/api/v1")
app.include_router(eval_router.router, prefix="/api/v1")
app.include_router(auth_router.router, prefix="/api/v1")
