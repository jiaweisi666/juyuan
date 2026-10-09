"""browser - 网关侧对受控浏览器的直接控制能力（CDP）。"""

from .cdp import (
    CDPError,
    apply_cookies,
    apply_login,
    parse_cookies,
    parse_storage,
    read_local_storage,
)

__all__ = [
    "CDPError",
    "apply_cookies",
    "apply_login",
    "parse_cookies",
    "parse_storage",
    "read_local_storage",
]
