import asyncio
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import docs_url, redoc_url, settings, validate_security_config
from app.database import async_session, engine
from app.utils import redis as redis_module

validate_security_config()
logger = logging.getLogger("schoolwall.requests")


@asynccontextmanager
async def lifespan(app):
    yield
    await engine.dispose()
    await redis_module.redis_client.aclose()


app = FastAPI(title="鄂应墙 API", version="1.0.0", docs_url=docs_url(),
              redoc_url=redoc_url(), openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json",
              lifespan=lifespan)
app.add_middleware(CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token", "X-Client-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"])

try:
    from prometheus_client import Counter, Histogram, CONTENT_TYPE_LATEST, generate_latest
    REQUESTS = Counter("schoolwall_http_requests_total", "API requests", ["method", "route", "status"])
    LATENCY = Histogram("schoolwall_http_duration_seconds", "API latency", ["method", "route"],
                        buckets=(.01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10))
except ImportError:
    REQUESTS = LATENCY = None


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("x-request-id", "")
    request.state.request_id = supplied if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", supplied) else uuid.uuid4().hex
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.error(json.dumps({"request_id": request.state.request_id, "event": "unhandled_error"}))
        response = JSONResponse(status_code=500, content={"code": 500, "message": "服务暂时不可用",
            "data": None, "request_id": request.state.request_id})
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    route = getattr(request.scope.get("route"), "path", "unmatched")
    elapsed = time.monotonic() - started
    if REQUESTS:
        REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        LATENCY.labels(request.method, route).observe(elapsed)
    logger.info(json.dumps({"request_id": request.state.request_id, "method": request.method,
        "route": route, "status": response.status_code, "elapsed_ms": round(elapsed * 1000, 2)}))
    return response


def _error(request, status, message, data=None):
    return JSONResponse(status_code=status, content={"code": status, "message": message, "data": data,
        "detail": message, "request_id": getattr(request.state, "request_id", None)})


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return _error(request, exc.status_code, exc.detail)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic's input field can contain passwords and proof data; never reflect it.
    errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return _error(request, 422, "请求参数不合法", errors)


@app.exception_handler(RedisError)
async def redis_error(request, exc):
    return _error(request, 503, "安全校验服务暂时不可用，请稍后重试")


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    return _error(request, 503, "数据服务暂时不可用，请稍后重试")


_static_dir = Path(settings.STATIC_BASE_DIR).resolve()
_static_dir.mkdir(parents=True, exist_ok=True)
# Legacy uploads are development-only; production media is authorized by its DB state.
if settings.ENVIRONMENT != "production":
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

from app.routers import activity, admin, admin_auth, auth, banner, interaction, notification, party, posts, tags, upload, user
from app.routers import student_verifications, moderation_jobs, appeals, block, runtime_controls, feedback

for module, prefix, tag in [
    (auth, "/auth", "Auth"), (user, "/user", "User"), (posts, "/posts", "Posts"),
    (interaction, "", "Interaction"), (notification, "", "Notification"), (party, "", "Party"),
    (upload, "/upload", "Upload"), (tags, "/tags", "Tags"), (activity, "", "Activity"),
    (admin, "/admin", "Admin"), (banner, "", "Banner"), (admin_auth, "/admin", "Admin Auth"),
    (student_verifications, "/student-verifications", "Student verification")]:
    app.include_router(module.router, prefix="/api/v1" + prefix, tags=[tag])
for module in (activity, tags, banner):
    app.include_router(module.admin_router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(student_verifications.admin_router, prefix="/api/v1/admin/student-verifications", tags=["Admin"])


app.include_router(runtime_controls.router, prefix="/api/v1", tags=["Operations"])
app.include_router(runtime_controls.admin_router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(block.router, prefix="/api/v1", tags=["Blocks"])
app.include_router(moderation_jobs.router, prefix="/api/v1/admin/moderation-jobs", tags=["Admin"])
app.include_router(appeals.router, prefix="/api/v1/appeals", tags=["Appeals"])
app.include_router(appeals.admin_router, prefix="/api/v1/admin/appeals", tags=["Admin"])
app.include_router(feedback.router, prefix="/api/v1/feedback", tags=["Feedback"])
app.include_router(feedback.admin_router, prefix="/api/v1/admin/feedback", tags=["Admin"])


@app.get("/health/live")
async def live():
    return {"status": "ok", "revision": settings.BUILD_REVISION}


@app.get("/health")
@app.get("/health/ready")
async def ready():
    try:
        async def check_database():
            async with async_session() as db:
                await db.execute(text("SELECT 1"))
        await asyncio.wait_for(check_database(), timeout=2)
        await asyncio.wait_for(redis_module.redis_client.ping(), timeout=2)
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable", "revision": settings.BUILD_REVISION})
    return {"status": "ok", "revision": settings.BUILD_REVISION}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    if REQUESTS is None:
        raise HTTPException(503, "Metrics unavailable")
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
