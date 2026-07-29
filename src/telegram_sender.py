import os
import html
import json
import time
import requests
import logging
from typing import Optional, Dict, Any
import core.config  # Carga centralizada del entorno.
from core.telegram_callback import build_callback

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def safe(value):
    """Escapa caracteres HTML y convierte a string"""
    return html.escape(str(value or ""))


def send_telegram_order(
    order_id: str,
    cliente_nombre: str,
    telefono: str,
    gmail: str,
    direccion: str,
    pedido: str,
    payment_method: str,
    total: Optional[str] = None,
    ubicacion: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Envía la notificación de nuevo pedido al grupo/chat de Telegram
    con botones inline para que el staff gestione el estado.
    """
    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("Telegram no configurado.")
        return False

    lat = None
    lng = None

    # Construir mensaje base
    message = (
        f"🍕 <b>NUEVO PEDIDO #{safe(order_id)}</b>\n\n"
        f"👤 <b>Cliente:</b> {safe(cliente_nombre)}\n"
        f"📞 <b>Teléfono:</b> {safe(telefono)}\n"
        f"📧 <b>Email:</b> {safe(gmail)}\n"
        f"📍 <b>Dirección:</b> {safe(direccion)}\n"
        f"🍕 <b>Pedido:</b> {safe(pedido)}\n"
        f"💰 <b>Total:</b> {safe(total or 'pendiente')}\n"
        f"💳 <b>Pago:</b> {safe(payment_method)}\n"
    )

    # Agregar ubicación detallada si existe
    if ubicacion:
        message += "\n🗺️ <b>UBICACIÓN PRECISA</b>\n"

        if isinstance(ubicacion, dict):
            if ubicacion.get("lat") is not None and ubicacion.get("lng") is not None:
                lat = float(ubicacion["lat"])
                lng = float(ubicacion["lng"])
                maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
                message += (
                    f"📌 <b>Coordenadas:</b> {lat:.6f}, {lng:.6f}\n"
                    f'🗺️ <a href="{maps_url}">Ver en Google Maps</a>\n'
                )

            if ubicacion.get("direccion_completa"):
                message += f"📍 <b>Dirección exacta:</b> {safe(ubicacion['direccion_completa'])}\n"

        elif isinstance(ubicacion, str):
            try:
                data = json.loads(ubicacion)
                if data.get("lat") is not None and data.get("lng") is not None:
                    lat = float(data["lat"])
                    lng = float(data["lng"])
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
                    message += f'🗺️ <a href="{maps_url}">Ver ubicación</a>\n'
            except Exception:
                message += f"📍 {safe(ubicacion)}\n"

    message += (
        "\n📌 <b>Estado:</b> PENDIENTE\n\n"
        "──────────────\n"
        "<b>GESTIÓN DEL PEDIDO</b>\n"
        "Presiona un botón:"
    )

    # Construir teclado inline
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ CONFIRMAR", "callback_data": build_callback("confirm", order_id)},
                {"text": "🍕 PREPARANDO", "callback_data": build_callback("preparing", order_id)}
            ],
            [
                {"text": "🛵 EN CAMINO", "callback_data": build_callback("delivery", order_id)},
                {"text": "🎉 ENTREGADO", "callback_data": build_callback("delivered", order_id)}
            ],
            [
                {"text": "❌ CANCELAR", "callback_data": build_callback("cancel", order_id)}
            ]
        ]
    }

    # Agregar botón de mapa si hay coordenadas
    if lat is not None and lng is not None:
        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
        keyboard["inline_keyboard"].append([
            {"text": "📍 VER MAPA", "url": maps_url}
        ])

    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "reply_markup": keyboard,
        "disable_web_page_preview": True
    }

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    logger.info("Enviando pedido a Telegram; order_id=%s", order_id)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=60)

            logger.info("Telegram respondió status=%s", response.status_code)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    logger.info("Pedido enviado a Telegram; order_id=%s", order_id)
                    
                    # Enviar ubicación como mensaje separado si hay coordenadas
                    if lat is not None and lng is not None:
                        send_telegram_location(order_id, lat, lng)
                    
                    return True
                else:
                    logger.warning("Telegram rechazó el mensaje.")
            else:
                logger.warning("Telegram respondió status=%s", response.status_code)

            if attempt < max_retries - 1:
                wait_time = attempt + 2
                logger.info("Reintentando Telegram en %s segundos.", wait_time)
                time.sleep(wait_time)

        except requests.exceptions.Timeout:
            logger.warning("Timeout de Telegram; intento=%s", attempt + 1)
            if attempt < max_retries - 1:
                time.sleep(3)
        except Exception:
            logger.exception("Error enviando pedido a Telegram.")
            if attempt < max_retries - 1:
                time.sleep(3)

    logger.error(
        "No se pudo enviar el pedido a Telegram; order_id=%s intentos=%s",
        order_id,
        max_retries,
    )
    return False


def send_telegram_location(order_id: str, latitude: float, longitude: float) -> bool:
    """
    Envía la ubicación como un mensaje de mapa separado en Telegram.
    Esto muestra un mapa interactivo dentro del chat.
    """
    if not BOT_TOKEN or not CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendLocation"

    payload = {
        "chat_id": CHAT_ID,
        "latitude": latitude,
        "longitude": longitude
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        logger.info("Telegram ubicación respondió status=%s", response.status_code)
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info("Ubicación enviada a Telegram; order_id=%s", order_id)
                return True
        return False
    except Exception:
        logger.exception("Error enviando ubicación a Telegram.")
        return False


def send_order_status_update(order_id: str, new_status: str) -> bool:
    """
    Envía una notificación de actualización de estado al chat de Telegram.
    """
    if not BOT_TOKEN or not CHAT_ID:
        return False
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    status_emojis = {
        "confirmado": "✅",
        "preparando": "🍕",
        "en camino": "🛵",
        "cancelado": "❌",
        "entregado": "🎉"
    }
    
    emoji = status_emojis.get(new_status, "📌")
    
    message = (
        f"{emoji} <b>ACTUALIZACIÓN DE PEDIDO #{safe(order_id)}</b>\n\n"
        f"📦 <b>Nuevo estado:</b> {new_status.upper()}\n\n"
        f"Gracias por tu paciencia 🍕"
    )
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                logger.info(
                    "Estado enviado a Telegram; order_id=%s status=%s",
                    order_id,
                    new_status,
                )
                return True
        return False
    except Exception:
        logger.exception("Error enviando actualización a Telegram.")
        return False
