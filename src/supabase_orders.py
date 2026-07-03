# src/supabase_orders.py

import os
import requests
import logging
import json
from typing import Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests.exceptions import RequestException
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

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

SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=RETRY_STRATEGY))
SESSION.mount("http://", HTTPAdapter(max_retries=RETRY_STRATEGY))


def create_order(data: dict) -> str | None:
    """Crea una nueva orden en Supabase y retorna su ID."""
    try:
        # Asegurar que ubicacion_maps sea string JSON válido
        if "ubicacion_maps" in data and isinstance(data["ubicacion_maps"], dict):
            data["ubicacion_maps"] = json.dumps(data["ubicacion_maps"])
        
        response = SESSION.post(
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


def update_order_status(order_id: str, status: str) -> bool:
    """Actualiza el estado de una orden."""
    try:
        print(f"\n🔄 Actualizando pedido {order_id}")
        print(f"📌 Nuevo estado: {status}")

        response = SESSION.patch(
            f"{SUPABASE_URL}/rest/v1/ordenes?id=eq.{order_id}",
            headers=HEADERS,
            json={"estado": status},
            timeout=30,
        )

        print("STATUS:", response.status_code)
        print("BODY:", response.text)

        if response.status_code not in [200, 204]:
            return False

        if response.status_code == 200:
            try:
                data = response.json()
                print("DATA:", data)
                if isinstance(data, list) and len(data) == 0:
                    print("❌ No existe pedido con ese ID")
                    return False
            except Exception:
                pass

        print("✅ Pedido actualizado")
        return True

    except Exception as e:
        print("❌ ERROR SUPABASE:", e)
        return False


def get_order_status(order_id: str) -> str:
    """
    Consulta el estado actual de una orden en Supabase.
    Usado por el frontend para hacer polling y mostrar
    al cliente las actualizaciones en tiempo casi-real.
    """
    try:
        response = SESSION.get(
            f"{SUPABASE_URL}/rest/v1/ordenes?id=eq.{order_id}&select=estado",
            headers=HEADERS,
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


def get_order_by_id(order_id: str) -> Optional[dict]:
    """Obtiene una orden completa por ID."""
    try:
        response = SESSION.get(
            f"{SUPABASE_URL}/rest/v1/ordenes?id=eq.{order_id}",
            headers=HEADERS,
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
        
        print(f"\n🔄 Actualizando información de pago para pedido {order_id}")
        print(f"📌 Datos: {data}")
        
        response = SESSION.patch(
            f"{SUPABASE_URL}/rest/v1/ordenes?id=eq.{order_id}",
            headers=HEADERS,
            json=data,
            timeout=30,
        )
        
        print("STATUS:", response.status_code)
        print("BODY:", response.text)
        
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