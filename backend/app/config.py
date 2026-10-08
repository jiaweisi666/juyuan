"""
config.py - 全局配置

所有配置通过环境变量（或 .env）读取，集中在 Settings 中，
其它模块统一通过 `get_settings()` 获取，避免散落的 os.getenv。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

try:  # python-dotenv 为可选，缺失时仍可运行（依赖真实环境变量）
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]


BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


def _load_env() -> None:
    if load_dotenv is None:
        return
    env_file = BACKEND_DIR / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)


def _env_str(key: str, default: str = "") -> str:
    value = os.getenv(key)
    return default if value is None else value.strip()


def _env_int(key: str, default: int) -> int:
    try:
        return int(str(os.getenv(key, "")).strip() or default)
    except (TypeError, ValueError):
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(str(os.getenv(key, "")).strip() or default)
    except (TypeError, ValueError):
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = str(os.getenv(key, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "y", "on"}


def _env_list(key: str, default: list[str]) -> list[str]:
    raw = str(os.getenv(key, "")).strip()
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass
class Settings:
    """运行期配置集合。"""

    # ---- 服务 ----
    host: str = "127.0.0.1"
    port: int = 8300
    debug: bool = True
    cors_origins: list[str] = field(default_factory=list)

    # ---- 鉴权 ----
    api_key: str = ""
    admin_token: str = ""

    # ---- 存储 ----
    data_dir: Path = field(default_factory=lambda: BACKEND_DIR / "data")
    secret_key: str = ""

    # ---- 账号池 / 防封号 ----
    account_rpm: int = 12
    cooldown_seconds: int = 90
    min_delay_seconds: float = 0.3
    max_delay_seconds: float = 1.2
    max_concurrency: int = 2
    keepalive_interval: int = 300

    # ---- AUTO 路由 ----
    auto_router_enabled: bool = True
    weight_accuracy: float = 0.5
    weight_latency: float = 0.2
    weight_cost: float = 0.3
    feedback_optimize: bool = True
    profile_refresh_interval: int = 3600

    # ---- 平台适配 ----
    real_browser_enabled: bool = False
    mock_fallback: bool = True
    vendor_dir: str = "../vendor/universal-web-api"
    base_web_api_url: str = "http://127.0.0.1:8199"
    base_web_api_key: str = ""
    # 动态模型目录（底座 /v1/models）缓存有效秒数
    model_cache_ttl: int = 600

    # ---- 派生路径 ----
    @property
    def db_path(self) -> Path:
        return self.data_dir / "gateway.db"

    @property
    def accounts_path(self) -> Path:
        return self.data_dir / "accounts.json"

    @property
    def routing_path(self) -> Path:
        return self.data_dir / "routing.json"

    @property
    def secret_path(self) -> Path:
        return self.data_dir / "secret.key"

    @property
    def vendor_path(self) -> Path:
        path = Path(self.vendor_dir)
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        return path

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


def _build_settings() -> Settings:
    _load_env()
    data_dir_raw = _env_str("GATEWAY_DATA_DIR", "")
    data_dir = Path(data_dir_raw).resolve() if data_dir_raw else (BACKEND_DIR / "data")
    return Settings(
        host=_env_str("GATEWAY_HOST", "127.0.0.1"),
        port=_env_int("GATEWAY_PORT", 8300),
        debug=_env_bool("GATEWAY_DEBUG", True),
        cors_origins=_env_list(
            "GATEWAY_CORS_ORIGINS",
            ["http://127.0.0.1:5273", "http://localhost:5273"],
        ),
        api_key=_env_str("GATEWAY_API_KEY", ""),
        admin_token=_env_str("GATEWAY_ADMIN_TOKEN", ""),
        data_dir=data_dir,
        secret_key=_env_str("GATEWAY_SECRET_KEY", ""),
        account_rpm=_env_int("GATEWAY_ACCOUNT_RPM", 12),
        cooldown_seconds=_env_int("GATEWAY_COOLDOWN_SECONDS", 90),
        min_delay_seconds=_env_float("GATEWAY_MIN_DELAY_SECONDS", 0.3),
        max_delay_seconds=_env_float("GATEWAY_MAX_DELAY_SECONDS", 1.2),
        max_concurrency=_env_int("GATEWAY_MAX_CONCURRENCY", 2),
        keepalive_interval=_env_int("GATEWAY_KEEPALIVE_INTERVAL", 300),
        auto_router_enabled=_env_bool("GATEWAY_AUTO_ROUTER_ENABLED", True),
        weight_accuracy=_env_float("GATEWAY_WEIGHT_ACCURACY", 0.5),
        weight_latency=_env_float("GATEWAY_WEIGHT_LATENCY", 0.2),
        weight_cost=_env_float("GATEWAY_WEIGHT_COST", 0.3),
        feedback_optimize=_env_bool("GATEWAY_FEEDBACK_OPTIMIZE", True),
        profile_refresh_interval=_env_int("GATEWAY_PROFILE_REFRESH_INTERVAL", 3600),
        real_browser_enabled=_env_bool("GATEWAY_REAL_BROWSER_ENABLED", False),
        mock_fallback=_env_bool("GATEWAY_MOCK_FALLBACK", True),
        vendor_dir=_env_str("GATEWAY_VENDOR_DIR", "../vendor/universal-web-api"),
        base_web_api_url=_env_str("GATEWAY_BASE_WEB_API_URL", "http://127.0.0.1:8199"),
        base_web_api_key=_env_str("GATEWAY_BASE_WEB_API_KEY", ""),
        model_cache_ttl=_env_int("GATEWAY_MODEL_CACHE_TTL", 600),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = _build_settings()
    settings.ensure_dirs()
    return settings


# 平台目录配置（内置平台定义 + 模型别名映射），随包分发
PLATFORMS_FILE = Path(__file__).resolve().parent / "resources" / "platforms.json"
