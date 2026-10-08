"""
crypto.py - 敏感信息加密。

使用 Fernet 对称加密存储账号 Cookie / SessionKey 等敏感字段。
密钥来源优先级：GATEWAY_SECRET_KEY 环境变量 > 本地 secret.key 文件（自动生成）。
"""

from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken

from ..config import get_settings
from ..logging_config import get_logger

logger = get_logger(__name__)

_fernet: Fernet | None = None


def _derive_key(raw: str) -> bytes:
    """将任意字符串派生出合法的 32 字节 urlsafe base64 密钥。"""
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _load_or_create_key() -> bytes:
    settings = get_settings()
    if settings.secret_key:
        return _derive_key(settings.secret_key)
    settings.ensure_dirs()
    secret_path = settings.secret_path
    if secret_path.exists():
        return secret_path.read_bytes().strip()
    key = Fernet.generate_key()
    secret_path.write_bytes(key)
    try:
        os.chmod(secret_path, 0o600)
    except OSError:
        pass
    logger.info("已生成新的本地加密密钥: %s", secret_path)
    return key


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    try:
        return get_fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask(secret: str, keep: int = 4) -> str:
    """脱敏展示：仅保留首尾少量字符。"""
    if not secret:
        return ""
    if len(secret) <= keep * 2:
        return "*" * len(secret)
    return f"{secret[:keep]}{'*' * 6}{secret[-keep:]}"
