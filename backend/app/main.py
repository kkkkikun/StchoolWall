from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import docs_url, redoc_url, settings, validate_security_config

validate_security_config()  # 启动即校验：生产密钥不合格直接拒绝启动

app = FastAPI(
    title="鄂应墙 API",
    version="0.1.0",
    docs_url=docs_url(),
    redoc_url=redoc_url(),
)

# CORS 白名单（Bearer 头鉴权无需 credentials 模式；小程序原生请求不走 CORS）
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """安全响应头：防内容嗅探与点击劫持（对 JSON API 与静态文件同样生效）。"""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# 本地静态资源（上传的图片等）：目录不存在时创建，否则 StaticFiles 启动即报错
_static_dir = Path(settings.STATIC_BASE_DIR).resolve()
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

from app.routers import admin, admin_auth, auth, banner, interaction, notification, party, posts, tags, upload, user  # noqa: E402

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(user.router, prefix="/api/v1/user", tags=["User"])
app.include_router(posts.router, prefix="/api/v1/posts", tags=["Posts"])
app.include_router(interaction.router, prefix="/api/v1", tags=["Interaction"])
app.include_router(notification.router, prefix="/api/v1", tags=["Notification"])
app.include_router(party.router, prefix="/api/v1", tags=["Party"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(tags.router, prefix="/api/v1/tags", tags=["Tags"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(banner.router, prefix="/api/v1", tags=["Banner"])
app.include_router(banner.admin_router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(admin_auth.router, prefix="/api/v1/admin", tags=["Admin Auth"])


@app.get("/health")
async def health_check():
    return {"status": "ok"}
