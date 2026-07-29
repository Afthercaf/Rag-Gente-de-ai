from __future__ import annotations
import logging
import os
from typing import Any, Optional

import requests
from core.config import require_env, supabase_server_key
logger = logging.getLogger(__name__)

SUPABASE_URL = require_env("SUPABASE_URL")
SUPABASE_KEY = supabase_server_key()

BASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}
RETURN_HEADERS = {**BASE_HEADERS, "Prefer": "return=representation"}
USERS_ENDPOINT = f"{SUPABASE_URL}/rest/v1/users"
TIMEOUT = (5, 20)

def _safe_log(operation: str, response: requests.Response) -> None:
    logger.info("%s STATUS=%s", operation, response.status_code)

def register_user(nombre: str, telefono: str, gmail: str, direccion: str, role: str = "cliente", password_hash: str = "") -> Optional[dict[str, Any]]:
    try:
        response = requests.post(
            USERS_ENDPOINT,
            headers=RETURN_HEADERS,
            json={
                "nombre": nombre,
                "telefono": telefono,
                "gmail": gmail.strip().lower(),
                "direccion": direccion,
                "role": role,
                "password_hash": password_hash,
            },
            timeout=TIMEOUT,
        )
        _safe_log("REGISTER", response)
        if response.status_code not in (200, 201):
            return None
        data = response.json()
        return data[0] if data else None
    except (requests.RequestException, ValueError, TypeError):
        logger.exception("Error registrando usuario")
        return None

def get_user_by_gmail(gmail: str) -> Optional[dict[str, Any]]:
    try:
        response = requests.get(
            USERS_ENDPOINT,
            headers=BASE_HEADERS,
            params={
                "gmail": f"eq.{gmail.strip().lower()}",
                "select": "id,public_id,nombre,telefono,gmail,direccion,role,password_hash,created_at",
                "limit": "1",
            },
            timeout=TIMEOUT,
        )
        _safe_log("GET_USER_BY_GMAIL", response)
        if response.status_code != 200:
            return None
        data = response.json()
        return data[0] if data else None
    except (requests.RequestException, ValueError, TypeError):
        logger.exception("Error obteniendo usuario")
        return None

def get_user_by_id(user_id: int) -> Optional[dict[str, Any]]:
    try:
        response = requests.get(
            USERS_ENDPOINT,
            headers=BASE_HEADERS,
            params={
                "id": f"eq.{int(user_id)}",
                "select": "id,public_id,nombre,telefono,gmail,direccion,role,created_at",
                "limit": "1",
            },
            timeout=TIMEOUT,
        )
        _safe_log("GET_USER_BY_ID", response)
        if response.status_code != 200:
            return None
        data = response.json()
        return data[0] if data else None
    except (requests.RequestException, ValueError, TypeError):
        logger.exception("Error obteniendo perfil de usuario")
        return None

def update_user_password_hash(user_id: int, password_hash: str) -> bool:
    try:
        response = requests.patch(
            USERS_ENDPOINT,
            headers=RETURN_HEADERS,
            params={"id": f"eq.{int(user_id)}", "select": "id"},
            json={"password_hash": password_hash},
            timeout=TIMEOUT,
        )
        _safe_log("UPDATE_PASSWORD_HASH", response)
        if response.status_code not in (200, 204):
            return False
        return True if response.status_code == 204 else bool(response.json())
    except (requests.RequestException, ValueError, TypeError):
        logger.exception("Error actualizando password_hash")
        return False

def login_user(gmail: str, password_hash: str | None = None):
    logger.warning("login_user está obsoleto; usa get_user_by_gmail + verify_password")
    return get_user_by_gmail(gmail)
