"""
main.py - FastAPI 应用入口。

组装网关：初始化日志、数据库、平台插件注册表、路由引擎，挂载
OpenAI / Anthropic 兼容接口、管理面板接口与统一对话窗口接口，
并在构建产物存在时托管前端静态资源。
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, logging_config
from .api import router as api_router
from .config import BACKEND_DIR, PROJECT_DIR, get_settings
from .logging_config import get_logger

logger = get_logger(__name__)

# 前端构建产物目录（Vite build 输出）
FRONTEND_DIST = PROJECT_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logging_config.setup_logging("DEBUG" if settings.debug else "INFO")
    logger.info("AI 模型聚合网关 v%s 启动中…", __version__)

    # 初始化核心组件（首次访问时构建，确保启动即校验配置）
    from .accounts.pool import get_pool
    from .platforms.registry import get_registry
    from .router.engine import get_router
    from .storage.db import get_database

    get_database()
    get_registry()
    get_pool()
    get_router()
    logger.info("核心组件初始化完成，监听 %s:%s", settings.host, settings.port)
    try:
        yield
    finally:
        logger.info("网关已停止")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="AI 模型聚合网关",
        description="多平台 Web2API 转换 + OpenAI/Anthropic 兼容 API + AUTO 智能路由",
        version=__version__,
        lifespan=lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request, exc):  # noqa: ANN001
        logger.exception("未处理异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(exc), "type": "internal_error"}},
        )

    # 托管前端（若已构建）
    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
