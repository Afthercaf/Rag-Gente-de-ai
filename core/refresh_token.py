"""Opaque, rotating refresh-token primitives.

Only a SHA-256 digest is retained. Raw bearer tokens never touch disk, and a
successful rotation revokes the previous token before issuing its replacement.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from typing import Optional

import redis

from core.config import require_env


REFRESH_TOKEN_EXPIRE_DAYS = 1
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
_REFRESH_TTL_SECONDS = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _redis_url() -> str:
    configured = os.getenv("REDIS_URL")
    if configured:
        return configured
    password = require_env("REDIS_PASSWORD")
    host = os.getenv("REDIS_HOST", "redis")
    port = os.getenv("REDIS_PORT", "6379")
    db = os.getenv("REDIS_DB", "0")
    return f"redis://:{password}@{host}:{port}/{db}"


class RefreshTokenManager:
    def __init__(self) -> None:
        self._redis = redis.Redis.from_url(
            _redis_url(),
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
        )
        # Solo se conserva para pruebas unitarias aisladas.
        self._tokens: dict[str, dict] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _key(token: str) -> str:
        return f"refresh:{_digest(token)}"

    @staticmethod
    def _testing() -> bool:
        return "PYTEST_CURRENT_TEST" in os.environ

    def create(self, user_id: int, ip_address: Optional[str] = None) -> str:
        token = secrets.token_urlsafe(48)
        now = int(time.time())
        record = {
            "user_id": int(user_id),
            "ip_address": ip_address,
            "used_count": 0,
            "created_at": now,
            "expires_at": now + _REFRESH_TTL_SECONDS,
        }
        if self._testing():
            with self._lock:
                self._tokens[_digest(token)] = record
        else:
            self._redis.setex(
                self._key(token),
                _REFRESH_TTL_SECONDS,
                json.dumps(record, separators=(",", ":")),
            )
        return token

    def validate(self, token: str) -> Optional[dict]:
        if not isinstance(token, str) or len(token) < 50:
            return None
        digest = _digest(token)
        now = int(time.time())
        if self._testing():
            with self._lock:
                record = self._tokens.get(digest)
                if record is None:
                    return None
                if record["expires_at"] <= now:
                    self._tokens.pop(digest, None)
                    return None
                return dict(record)
        raw = self._redis.get(self._key(token))
        if raw is None:
            return None
        record = json.loads(raw)
        if int(record.get("expires_at", 0)) <= now:
            self._redis.delete(self._key(token))
            return None
        return record

    def revoke(self, token: str) -> bool:
        if self._testing():
            with self._lock:
                return self._tokens.pop(_digest(token), None) is not None
        return bool(self._redis.delete(self._key(token)))

    def rotate(self, token: str, ip_address: Optional[str] = None) -> Optional[str]:
        if self._testing():
            with self._lock:
                record = self.validate(token)
                if record is None:
                    return None
                self._tokens.pop(_digest(token), None)
                return self.create(record["user_id"], ip_address)
        raw = self._redis.getdel(self._key(token))
        if raw is None:
            return None
        record = json.loads(raw)
        if int(record.get("expires_at", 0)) <= int(time.time()):
            return None
        return self.create(int(record["user_id"]), ip_address)

    def cleanup_expired(self) -> int:
        if not self._testing():
            # Redis elimina automáticamente las claves por TTL.
            return 0
        now = int(time.time())
        with self._lock:
            expired = [
                key for key, value in self._tokens.items()
                if value["expires_at"] <= now
            ]
            for key in expired:
                self._tokens.pop(key, None)
            return len(expired)


refresh_token_manager = RefreshTokenManager()


def create_refresh_token(user_id: int, ip_address: Optional[str] = None) -> str:
    return refresh_token_manager.create(user_id, ip_address)


def validate_refresh_token(token: str) -> Optional[dict]:
    return refresh_token_manager.validate(token)


def rotate_refresh_token(token: str, ip_address: Optional[str] = None) -> Optional[str]:
    return refresh_token_manager.rotate(token, ip_address)


def revoke_refresh_token(token: str) -> bool:
    return refresh_token_manager.revoke(token)
