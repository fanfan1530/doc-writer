"""API Key 加密工具 —— 使用 Fernet 对称加密保护存储的 API Key。"""

import os
from pathlib import Path

from cryptography.fernet import Fernet

_KEY_PATH = Path(__file__).resolve().parent.parent / "knowledge" / ".fernet_key"
_key: Fernet | None = None


def _load_or_create_key() -> Fernet:
    global _key
    if _key is not None:
        return _key
    env_key = os.getenv("FERNET_KEY", "")
    if env_key:
        _key = Fernet(env_key.encode())
        return _key
    if _KEY_PATH.exists():
        _key = Fernet(_KEY_PATH.read_bytes())
        return _key
    _key = Fernet.generate_key()
    _KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KEY_PATH.write_bytes(_key)
    _key = Fernet(_key)
    return _key


def encrypt_api_key(plain: str) -> str:
    if not plain or plain.startswith("gAAAAA"):
        return plain
    f = _load_or_create_key()
    return f.encrypt(plain.encode()).decode()


def decrypt_api_key(encrypted: str) -> str:
    if not encrypted:
        return ""
    if encrypted.startswith("gAAAAA"):
        try:
            f = _load_or_create_key()
            return f.decrypt(encrypted.encode()).decode()
        except Exception:
            return encrypted
    return encrypted
