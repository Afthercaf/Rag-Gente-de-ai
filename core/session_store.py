"""
Session store con Redis + encriptación AES-GCM.

Cada sesión se almacena como un blob JSON encriptado con AES-256-GCM.
La clave se deriva de SESSION_ENCRYPTION_KEY mediante HKDF.

Formato en Redis:
  key:  session:{user_id}
  value: nonce_base64 || ciphertext_base64
  TTL:  configurable (default 24h)
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any, Dict, Optional

from core.config import require_env
from core.crypto import derive_aes_key, encrypt_json, decrypt_json

logger = logging.getLogger(__name__)


def _build_redis_url_from_parts() -> str:
    """Construye REDIS_URL a partir de variables separadas (VULN-04)."""
    host = os.getenv("REDIS_HOST", "redis")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))
    password = require_env("REDIS_PASSWORD")
    return f"redis://:{password}@{host}:{port}/{db}"


# ─────────────────────────────────────────────────────────────
# Configuración desde variables de entorno
# ─────────────────────────────────────────────────────────────

# VULN-04: no incluir contraseña en URL; se construye en runtime si no existe.
REDIS_URL = os.getenv(
    "REDIS_URL",
    _build_redis_url_from_parts(),
)
SESSION_ENCRYPTION_KEY = require_env("SESSION_ENCRYPTION_KEY", min_length=32)
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "86400"))  # 24h

_SESSION_DOMAIN = b"pizzeria220-session-store-v1"
_AES_KEY = derive_aes_key(SESSION_ENCRYPTION_KEY, _SESSION_DOMAIN)


# ─────────────────────────────────────────────────────────────
# Singleton del store
# ─────────────────────────────────────────────────────────────

class SessionStore:
    """Almacén de sesiones en Redis con encriptación extrema a extremo."""

    def __init__(self, redis_url: str = REDIS_URL, ttl: int = SESSION_TTL_SECONDS):
        self._redis_url = redis_url
        self._ttl = ttl
        self._redis = None
        self._sync_redis = None
        self._lock = threading.Lock()

    # ── Lazy connection ──────────────────────────────────────

    @property
    def redis(self):
        if self._redis is None:
            with self._lock:
                if self._redis is None:
                    import redis.asyncio as aioredis
                    self._redis = aioredis.from_url(
                        self._redis_url,
                        decode_responses=False,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                        health_check_interval=30,
                    )
        return self._redis

    @property
    def sync_redis(self):
        if self._sync_redis is None:
            with self._lock:
                if self._sync_redis is None:
                    import redis
                    self._sync_redis = redis.Redis.from_url(
                        self._redis_url,
                        decode_responses=False,
                        socket_connect_timeout=5,
                        socket_timeout=5,
                        retry_on_timeout=True,
                        health_check_interval=30,
                    )
        return self._sync_redis

    async def close(self):
        """Cierra la conexión Redis."""
        if self._redis is not None:
            await self._redis.close()
            self._redis = None
        if self._sync_redis is not None:
            self._sync_redis.close()
            self._sync_redis = None

    # ── Clave en Redis ───────────────────────────────────────

    @staticmethod
    def _key(user_id: int) -> str:
        return f"session:{user_id}"

    # ── Operaciones CRUD ─────────────────────────────────────

    async def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Obtiene la sesión de un usuario, desencriptada."""
        try:
            raw = await self.redis.get(self._key(user_id))
            if raw is None:
                return None
            return decrypt_json(raw, _AES_KEY)
        except Exception as exc:
            logger.error("Error leyendo sesión de Redis: %s", exc)
            return None

    def get_sync(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Lee una sesión desde código síncrono sin bloquear el event loop."""
        try:
            raw = self.sync_redis.get(self._key(user_id))
            if raw is None:
                return None
            return decrypt_json(raw, _AES_KEY)
        except Exception as exc:
            logger.error("Error leyendo sesión de Redis: %s", exc)
            return None

    def set_sync(self, user_id: int, data: Dict[str, Any]) -> bool:
        """Persiste inmediatamente una sesión desde código síncrono."""
        try:
            encrypted = encrypt_json(data, _AES_KEY)
            self.sync_redis.setex(self._key(user_id), self._ttl, encrypted)
            return True
        except Exception as exc:
            logger.error("Error guardando sesión en Redis: %s", exc)
            return False

    async def set(self, user_id: int, data: Dict[str, Any]) -> bool:
        """Guarda y encripta la sesión de un usuario en Redis."""
        try:
            encrypted = encrypt_json(data, _AES_KEY)
            await self.redis.setex(self._key(user_id), self._ttl, encrypted)
            return True
        except Exception as exc:
            logger.error("Error guardando sesión en Redis: %s", exc)
            return False

    async def delete(self, user_id: int) -> bool:
        """Elimina la sesión de un usuario de Redis."""
        try:
            await self.redis.delete(self._key(user_id))
            return True
        except Exception as exc:
            logger.error("Error eliminando sesión de Redis: %s", exc)
            return False

    async def touch(self, user_id: int) -> bool:
        """Renueva el TTL de una sesión activa."""
        try:
            await self.redis.expire(self._key(user_id), self._ttl)
            return True
        except Exception as exc:
            logger.error("Error renovando TTL de sesión: %s", exc)
            return False

    async def exists(self, user_id: int) -> bool:
        """Verifica si existe una sesión para el usuario."""
        try:
            return bool(await self.redis.exists(self._key(user_id)))
        except Exception as exc:
            logger.error("Error verificando existencia de sesión: %s", exc)
            return False

    async def clear_all(self) -> int:
        """Elimina TODAS las sesiones. Útil para reinicios.
        
        Returns: cantidad de sesiones eliminadas.
        """
        try:
            cursor = 0
            deleted = 0
            pattern = "session:*"
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor, match=pattern, count=100
                )
                if keys:
                    await self.redis.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as exc:
            logger.error("Error limpiando sesiones de Redis: %s", exc)
            return 0

    async def active_count(self) -> int:
        """Cantidad de sesiones activas en Redis."""
        try:
            cursor = 0
            count = 0
            while True:
                cursor, keys = await self.redis.scan(
                    cursor=cursor, match="session:*", count=500
                )
                count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception as exc:
            logger.error("Error contando sesiones activas: %s", exc)
            return 0


# Instancia global del store (singleton)
session_store = SessionStore()
