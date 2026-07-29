import os
import logging
import requests
import uuid
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from core.config import require_env, supabase_server_key
from core.crypto import decrypt_json, derive_aes_key, encrypt_json

logger = logging.getLogger(__name__)

SUPABASE_URL = require_env("SUPABASE_URL")
SUPABASE_KEY = supabase_server_key()
_CHAT_KEY = derive_aes_key(
    require_env("SESSION_ENCRYPTION_KEY", min_length=32),
    b"pizzeria220-chat-history-v1",
)
_ENCRYPTED_PREFIX = "enc:v1:"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

TABLE_NAME = "chat_history"
SESSION = requests.Session()
SESSION.mount(
    "https://",
    HTTPAdapter(max_retries=Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PATCH", "DELETE"],
    )),
)


def _encrypt_content(content: str) -> str:
    return _ENCRYPTED_PREFIX + encrypt_json({"content": content}, _CHAT_KEY)


def _decrypt_content(content: str) -> str | None:
    if not content.startswith(_ENCRYPTED_PREFIX):
        return content
    payload = decrypt_json(content[len(_ENCRYPTED_PREFIX):], _CHAT_KEY)
    value = payload.get("content") if payload else None
    return value if isinstance(value, str) else None


def _migrate_legacy_row(row: dict) -> None:
    row_id = row.get("id")
    content = row.get("content")
    if row_id is None or not isinstance(content, str) or content.startswith(_ENCRYPTED_PREFIX):
        return
    try:
        SESSION.patch(
            f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}",
            headers=HEADERS,
            params={"id": f"eq.{row_id}"},
            json={"content": _encrypt_content(content)},
            timeout=(5, 20),
        )
    except requests.RequestException:
        logger.warning("No se pudo migrar una fila histórica de chat.")


def insert_chat_history(user_id: int, role: str, content: str) -> bool:
    """Inserta un mensaje de chat en la tabla Supabase chat_history."""
    try:
        validated_id = _validate_user_id(user_id)
        payload = [{
            "user_id": validated_id,
            "role": role,
            "content": _encrypt_content(content),
        }]
        response = SESSION.post(
            f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}",
            headers=HEADERS,
            json=payload,
            timeout=(5, 20),
        )
        if response.status_code in (200, 201):
            return True
        logger.warning("No se pudo insertar chat_history; status=%s", response.status_code)
        return False
    except Exception as e:
        logger.exception("Error insert_chat_history: %s", e)
        return False


def get_chat_history(user_id: int, limit: int = 50) -> list[dict]:
    """Obtiene el historial de chat de un usuario desde Supabase."""
    try:
        validated_id = _validate_user_id(user_id)
        safe_limit = max(1, min(int(limit), 100))
        params = {
            "user_id": f"eq.{validated_id}",
            "select": "id,user_id,role,content,created_at",
            "order": "created_at.desc",
            "limit": str(safe_limit),
        }
        response = SESSION.get(
            f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}",
            headers=HEADERS,
            params=params,
            timeout=(5, 20),
        )
        if response.status_code == 200:
            data = response.json()
            safe_rows = []
            for row in data:
                raw_content = row.get("content")
                if not isinstance(raw_content, str):
                    continue
                plain_content = _decrypt_content(raw_content)
                if plain_content is None:
                    logger.warning("Fila de chat cifrada inválida omitida.")
                    continue
                _migrate_legacy_row(row)
                safe_rows.append({**row, "content": plain_content})
            return list(reversed(safe_rows))
        logger.warning("No se pudo leer chat_history; status=%s", response.status_code)
        return []
    except Exception as e:
        logger.exception("Error get_chat_history: %s", e)
        return []


def _validate_user_id(user_id: int) -> int:
    """Valida que user_id sea un entero positivo."""
    user_id = int(user_id)
    if user_id <= 0:
        raise ValueError("user_id debe ser un entero positivo")
    return user_id


def delete_chat_history(user_id: int) -> bool:
    """Elimina el historial de chat de un usuario en Supabase."""
    try:
        validated_id = _validate_user_id(user_id)
        response = SESSION.delete(
            f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}",
            headers=HEADERS,
            params={"user_id": f"eq.{validated_id}"},
            timeout=(5, 20),
        )
        if response.status_code in (200, 204):
            return True
        logger.warning("No se pudo eliminar chat_history; status=%s", response.status_code)
        return False
    except Exception as e:
        logger.exception("Error delete_chat_history: %s", e)
        return False
