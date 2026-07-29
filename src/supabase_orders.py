# src/supabase_orders.py

import os
import requests
import logging
import json
import uuid
import threading
from typing import Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException
from core.config import require_env, supabase_server_key

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

SUPABASE_URL = require_env("SUPABASE_URL")
SUPABASE_KEY = supabase_server_key()

HEADERS = {
    "apikey":        SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=representation",
}

RETRY_STRATEGY = Retry(
    total=3,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PATCH"],
    backoff_factor=1,
)

_SESSION_LOCAL = threading.local()


def _session() -> requests.Session:
    session = getattr(_SESSION_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        session.mount("https://", HTTPAdapter(max_retries=RETRY_STRATEGY))
        session.mount("http://", HTTPAdapter(max_retries=RETRY_STRATEGY))
        _SESSION_LOCAL.session = session
    return session


def create_order(data: dict) -> str | None:
    """Crea una nueva orden en Supabase y retorna su ID."""
    try:
        # Asegurar que ubicacion_maps sea string JSON válido
        if "ubicacion_maps" in data and isinstance(data["ubicacion_maps"], dict):
            data["ubicacion_maps"] = json.dumps(data["ubicacion_maps"])
        
        response = _session().post(
            f"{SUPABASE_URL}/rest/v1/ordenes",
            headers=HEADERS,
            json=data,
            timeout=30,
        )
        if response.status_code in [200, 201]:
            result = response.json()
            if result:
                order_id = result[0]["id"]
                logger.info(f"Orden creada con ID: {order_id}")
                return order_id
        logger.error(f"Error creando orden: {response.text}")
        return None
    except Exception as e:
        logger.error(f"Error en create_order: {e}")
        return None


def update_order_status(order_id: str, status: str, owner_user_id: int | None = None) -> bool:
    """Actualiza el estado de una orden.

    Si owner_user_id se proporciona, solo actualiza si el pedido pertenece
    a ese usuario (VULN-08/09).
    """
    try:
        validated_id = _validate_uuid(order_id)
        logger.info("Actualizando estado de pedido")

        params = {"id": f"eq.{validated_id}"}
        if owner_user_id is not None:
            params["user_id"] = f"eq.{owner_user_id}"

        response = _session().patch(
            f"{SUPABASE_URL}/rest/v1/ordenes",
            headers=HEADERS,
            params=params,
            json={"estado": status},
            timeout=30,
        )

        logger.info("Supabase update status=%s", response.status_code)

        if response.status_code not in [200, 204]:
            return False

        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, list) and len(data) == 0:
                    logger.info("Pedido no encontrado o no autorizado")
                    return False
            except Exception:
                pass

        logger.info("Pedido actualizado")
        return True

    except Exception as e:
        logger.exception("Error actualizando pedido en Supabase")
        return False


def _validate_uuid(value: str, field_name: str = "order_id") -> str:
    """Valida que el valor sea un UUID válido y lo retorna."""
    try:
        uuid.UUID(str(value))
        return str(value)
    except (ValueError, AttributeError):
        raise ValueError(f"{field_name} debe ser un UUID válido")


def get_order_status(order_id: str) -> str:
    """
    Consulta el estado actual de una orden en Supabase.
    Usado por el frontend para hacer polling y mostrar
    al cliente las actualizaciones en tiempo casi-real.
    """
    try:
        validated_id = _validate_uuid(order_id)
        response = _session().get(
            f"{SUPABASE_URL}/rest/v1/ordenes",
            headers=HEADERS,
            params={
                "id": f"eq.{validated_id}",
                "select": "estado",
            },
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0]["estado"]
            logger.warning(f"Orden {order_id} no encontrada")
            return "desconocido"
        logger.error(f"Error consultando estado: {response.text}")
        return "desconocido"
    except Exception as e:
        logger.error(f"Error en get_order_status: {e}")
        return "desconocido"


def _get_all_orders(limit: int = 1000) -> list[dict]:
    """Obtiene órdenes para estadísticas de ventas.

    La tabla ``ordenes`` no tiene una columna ``producto``. El detalle del
    pedido se conserva principalmente en ``pedido`` y, para registros nuevos,
    puede complementarse con ``pizza``, ``extras`` y ``cantidad``.

    Esta función degrada a una lista vacía si Supabase no está disponible.
    """
    try:
        safe_limit = max(1, min(int(limit), 5000))

        select_fields = (
            "id,user_id,pedido,pizza,extras,cantidad,total,"
            "estado,created_at"
        )

        response = _session().get(
            f"{SUPABASE_URL}/rest/v1/ordenes"
            f"?select={select_fields}"
            f"&estado=neq.cancelado"
            f"&order=created_at.desc"
            f"&limit={safe_limit}",
            headers=HEADERS,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else []

        logger.warning(
            "No se pudieron leer órdenes. Status=%s Body=%s",
            response.status_code,
            response.text,
        )
        return []

    except (TypeError, ValueError):
        logger.warning("Límite inválido en _get_all_orders: %r", limit)
        return []
    except Exception as e:
        logger.error(f"Error en _get_all_orders: {e}")
        return []


def get_order_by_id(order_id: str) -> Optional[dict]:
    """Obtiene una orden completa por ID."""
    try:
        validated_id = _validate_uuid(order_id)
        response = _session().get(
            f"{SUPABASE_URL}/rest/v1/ordenes",
            headers=HEADERS,
            params={"id": f"eq.{validated_id}"},
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0]
        return None
    except Exception as e:
        logger.error(f"Error en get_order_by_id: {e}")
        return None


def get_order_by_id_and_owner(order_id: str, owner_user_id: int) -> Optional[dict]:
    """Obtiene una orden solo si pertenece al usuario indicado (VULN-08/09)."""
    try:
        validated_id = _validate_uuid(order_id)
        response = _session().get(
            f"{SUPABASE_URL}/rest/v1/ordenes",
            headers=HEADERS,
            params={
                "id": f"eq.{validated_id}",
                "user_id": f"eq.{owner_user_id}",
            },
            timeout=30,
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0]
        return None
    except Exception as e:
        logger.error(f"Error en get_order_by_id_and_owner: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════
# NUEVA FUNCIÓN: Actualizar información de pago
# ═══════════════════════════════════════════════════════════════════

def update_payment_info(
    order_id: int,
    payment_id: str,
    payment_url: str,
    payment_status: str,
    preference_id: Optional[str] = None,
) -> bool:
    """
    Actualiza la información de pago en la tabla ordenes.
    
    Args:
        order_id: ID del pedido
        payment_id: ID del pago en Mercado Pago
        payment_url: URL del link de pago
        payment_status: Estado del pago (pending, approved, etc.)
        preference_id: ID de la preferencia (opcional, por defecto usa payment_id)
    
    Returns:
        True si se actualizó correctamente, False en caso contrario
    """
    try:
        logger.info(f"💳 Actualizando información de pago para orden {order_id}")
        logger.info(f"   Payment ID: {payment_id}")
        logger.info(f"   Payment URL: {payment_url}")
        logger.info(f"   Payment Status: {payment_status}")
        
        # Construir datos a actualizar
        data = {
            "payment_id": payment_id,
            "payment_url": payment_url,
            "payment_status": payment_status,
        }
        
        # Si no se proporciona preference_id, usar payment_id
        if preference_id:
            data["preference_id"] = preference_id
        else:
            data["preference_id"] = payment_id
        
        logger.info("Actualizando información de pago")
        
        validated_id = _validate_uuid(str(order_id))
        response = _session().patch(
            f"{SUPABASE_URL}/rest/v1/ordenes",
            headers=HEADERS,
            params={"id": f"eq.{validated_id}"},
            json=data,
            timeout=30,
        )
        
        logger.info("Supabase payment update status=%s", response.status_code)
        
        if response.status_code not in [200, 204]:
            logger.error(f"❌ Error actualizando pago: {response.text}")
            return False
        
        if response.status_code == 200:
            try:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    logger.info(f"✅ Información de pago actualizada para orden {order_id}")
                    return True
                else:
                    logger.warning(f"⚠️ No se encontró la orden {order_id}")
                    return False
            except Exception:
                pass
        
        logger.info(f"✅ Información de pago actualizada para orden {order_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en update_payment_info: {e}")
        return False
