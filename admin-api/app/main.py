# ================================================================
# 安全情报分析智能体 — 管理 API 主应用入口
# 版本：v1.0
# 作者：alex (unix_sec@163.com)
# 日期：2026-03-04
# ================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routes import audit, config, dashboard, intel, reports, sources

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "安全情报分析智能体管理后台 API\n\n"
        "提供情报源管理、关键词管理、情报查询、报告管理、系统配置等接口。\n\n"
        "作者：alex (unix_sec@163.com)"
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由挂载（统一前缀 /api/v1）
API_PREFIX = "/api/v1"

app.include_router(sources.router, prefix=API_PREFIX)
app.include_router(intel.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(config.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.app_name, "version": settings.app_version}


@app.get("/health", tags=["系统"])
def health():
    """服务存活检查（K8s liveness probe）。"""
    return {"status": "ok", "version": settings.app_version}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务错误，请联系管理员"},
    )
