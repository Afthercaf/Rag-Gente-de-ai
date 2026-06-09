import os
import html
import json
import time
import requests
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

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
    ubicacion: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Envía la notificación de nuevo pedido al grupo/chat de Telegram
    con botones inline para que el staff gestione el estado.
    """
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Telegram no configurado (BOT_TOKEN o CHAT_ID faltantes)")
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
                {"text": "✅ CONFIRMAR", "callback_data": f"confirm_{order_id}"},
                {"text": "🍕 PREPARANDO", "callback_data": f"preparing_{order_id}"}
            ],
            [
                {"text": "🛵 EN CAMINO", "callback_data": f"delivery_{order_id}"},
                {"text": "🎉 ENTREGADO", "callback_data": f"delivered_{order_id}"}
            ],
            [
                {"text": "❌ CANCELAR", "callback_data": f"cancel_{order_id}"}
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

    print(f"📤 Enviando pedido #{order_id} a Telegram...")
    if ubicacion:
        print(f"📍 Con ubicación: {ubicacion}")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=60)

            print(f"STATUS: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print(f"✅ Pedido #{order_id} enviado a Telegram correctamente")
                    
                    # Enviar ubicación como mensaje separado si hay coordenadas
                    if lat is not None and lng is not None:
                        send_telegram_location(order_id, lat, lng)
                    
                    return True
                else:
                    print(f"❌ Error en respuesta de Telegram: {result}")
            else:
                print(f"❌ Error HTTP {response.status_code}: {response.text[:200]}")

            if attempt < max_retries - 1:
                wait_time = attempt + 2
                print(f"🔄 Reintentando en {wait_time} segundos...")
                time.sleep(wait_time)

        except requests.exceptions.Timeout:
            print(f"⚠️ Timeout (intento {attempt + 1})")
            if attempt < max_retries - 1:
                time.sleep(3)
        except Exception as e:
            print(f"❌ Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)

    print(f"❌ No se pudo enviar el pedido #{order_id} a Telegram tras {max_retries} intentos")
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
        print(f"📍 MAP STATUS: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print(f"✅ Ubicación del pedido #{order_id} enviada a Telegram")
                return True
        return False
    except Exception as e:
        print(f"❌ Error enviando ubicación a Telegram: {e}")
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
                print(f"✅ Actualización de estado #{order_id} -> {new_status} enviada")
                return True
        return False
    except Exception as e:
        print(f"❌ Error enviando actualización: {e}")
        return False