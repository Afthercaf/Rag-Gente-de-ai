import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL no definida")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY no definida")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

TABLE_NAME = "chat_history"


def insert_chat_history(user_id: int, role: str, content: str) -> bool:
    """Inserta un mensaje de chat en la tabla Supabase chat_history."""
    try:
        payload = [{
            "user_id": user_id,
            "role": role,
            "content": content,
        }]
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}",
            headers=HEADERS,
            json=payload,
            timeout=(5, 20),
        )
        if response.status_code in (200, 201):
            return True
        logger.warning("No se pudo insertar chat_history: %s", response.text)
        return False
    except Exception as e:
        logger.exception("Error insert_chat_history: %s", e)
        return False


def get_chat_history(user_id: int, limit: int = 50) -> list[dict]:
    """Obtiene el historial de chat de un usuario desde Supabase."""
    try:
        params = {
            "user_id": f"eq.{user_id}",
            "select": "id,user_id,role,content,created_at",
            "order": "created_at.desc",
            "limit": str(limit),
        }
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}",
            headers=HEADERS,
            params=params,
            timeout=(5, 20),
        )
        if response.status_code == 200:
            data = response.json()
            return list(reversed(data))
        logger.warning("No se pudo leer chat_history: %s", response.text)
        return []
    except Exception as e:
        logger.exception("Error get_chat_history: %s", e)
        return []


def delete_chat_history(user_id: int) -> bool:
    """Elimina el historial de chat de un usuario en Supabase."""
    try:
        response = requests.delete(
            f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?user_id=eq.{user_id}",
            headers=HEADERS,
            timeout=(5, 20),
        )
        if response.status_code in (200, 204):
            return True
        logger.warning("No se pudo eliminar chat_history: %s", response.text)
        return False
    except Exception as e:
        logger.exception("Error delete_chat_history: %s", e)
        return False
