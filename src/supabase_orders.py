# src/supabase_orders.py

import os
import requests
import logging
import json
from typing import Optional
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


def create_order(data: dict) -> str | None:
    """Crea una nueva orden en Supabase y retorna su ID."""
    try:
        # Asegurar que ubicacion_maps sea string JSON válido
        if "ubicacion_maps" in data and isinstance(data["ubicacion_maps"], dict):
            data["ubicacion_maps"] = json.dumps(data["ubicacion_maps"])
        
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/ordenes",
            headers=HEADERS,
            json=data,
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
    """Actualiza el estado de una orden existente."""
    try:
        if not order_id:
            logger.warning("update_order_status: order_id vacío")
            return False

        response = requests.patch(
            f"{SUPABASE_URL}/rest/v1/ordenes?id=eq.{order_id}",
            headers=HEADERS,
            json={"estado": status},
        )
        if response.status_code in [200, 204]:
            logger.info(f"Pedido {order_id} actualizado a: {status}")
            return True

        logger.warning(f"No se pudo actualizar pedido {order_id}: {response.text}")
        return False
    except Exception as e:
        logger.error(f"Error en update_order_status: {e}")
        return False


def get_order_status(order_id: str) -> str:
    """Consulta el estado actual de una orden."""
    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/ordenes?id=eq.{order_id}&select=estado",
            headers=HEADERS,
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
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/ordenes?id=eq.{order_id}",
            headers=HEADERS,
        )
        if response.status_code == 200:
            data = response.json()
            if data:
                return data[0]
        return None
    except Exception as e:
        logger.error(f"Error en get_order_by_id: {e}")
        return None