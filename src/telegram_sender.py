# src/telegram_sender.py

import os
import requests
import time
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram_order(
    order_id:       str,
    cliente_nombre: str,
    telefono:       str,
    gmail:          str,
    direccion:      str,
    pedido:         str,
    payment_method: str,
    ubicacion:      Optional[Dict[str, Any]] = None,  # Nuevo parámetro
) -> bool:
    """
    Envía la notificación de nuevo pedido al grupo/chat de Telegram
    con botones inline para que el staff gestione el estado.
    
    Args:
        ubicacion: Diccionario con {lat, lng, direccion_completa, ...}
    """
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Telegram no configurado (BOT_TOKEN o CHAT_ID faltantes)")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    # Construir mensaje base
    message = (
        f"🍕 **NUEVO PEDIDO #{order_id}**\n\n"
        f"👤 *Cliente:* {cliente_nombre}\n"
        f"📞 *Teléfono:* {telefono}\n"
        f"📧 *Email:* {gmail}\n"
        f"📍 *Dirección:* {direccion}\n"
        f"🍕 *Pedido:* {pedido}\n"
        f"💳 *Pago:* {payment_method}\n"
    )
    
    # Agregar ubicación detallada si existe
    if ubicacion:
        message += f"\n🗺️ **UBICACIÓN PRECISA:**\n"
        
        if isinstance(ubicacion, dict):
            # Si viene como dict con lat/lng
            if "lat" in ubicacion and "lng" in ubicacion:
                message += f"📌 *Coordenadas:* {ubicacion['lat']:.6f}, {ubicacion['lng']:.6f}\n"
                # Crear link a Google Maps
                maps_url = f"https://www.google.com/maps?q={ubicacion['lat']},{ubicacion['lng']}"
                message += f"🗺️ [Ver en Google Maps]({maps_url})\n"
            
            # Si tiene dirección completa
            if "direccion_completa" in ubicacion and ubicacion["direccion_completa"]:
                message += f"📍 *Dirección exacta:* {ubicacion['direccion_completa']}\n"
        
        elif isinstance(ubicacion, str):
            # Si es string JSON, parsearlo
            try:
                import json
                ubicacion_dict = json.loads(ubicacion)
                if "lat" in ubicacion_dict and "lng" in ubicacion_dict:
                    maps_url = f"https://www.google.com/maps?q={ubicacion_dict['lat']},{ubicacion_dict['lng']}"
                    message += f"🗺️ [Ver ubicación en Google Maps]({maps_url})\n"
            except:
                message += f"📍 *Ubicación:* {ubicacion}\n"
    
    message += f"\n📌 *Estado:* PENDIENTE\n\n"
    message += f"--- GESTIÓN DEL PEDIDO ---\n"
    message += f"Presiona un botón para actualizar el estado:"

    # Teclado inline con las acciones posibles
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ CONFIRMAR",  "callback_data": f"confirm_{order_id}"},
                {"text": "🍕 PREPARANDO", "callback_data": f"preparing_{order_id}"},
            ],
            [
                {"text": "🛵 EN CAMINO", "callback_data": f"delivery_{order_id}"},
                {"text": "❌ CANCELAR",  "callback_data": f"cancel_{order_id}"},
            ],
            [
                {"text": "📍 VER MAPA", "url": f"https://www.google.com/maps/search/?api=1&query={ubicacion.get('lat', '')},{ubicacion.get('lng', '')}" if ubicacion and isinstance(ubicacion, dict) and 'lat' in ubicacion else "#"},
            ] if ubicacion and isinstance(ubicacion, dict) and 'lat' in ubicacion else []
        ]
    }
    
    # Limpiar filas vacías
    keyboard["inline_keyboard"] = [row for row in keyboard["inline_keyboard"] if row]

    payload = {
        "chat_id":      CHAT_ID,
        "text":         message,
        "reply_markup": keyboard,
        "parse_mode":   "Markdown",  # Para usar negritas y links
    }

    print(f"📤 Enviando pedido {order_id} a Telegram...")
    if ubicacion:
        print(f"📍 Con ubicación: {ubicacion}")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=payload, timeout=60)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print(f"✅ Pedido {order_id} enviado a Telegram correctamente")
                    
                    # Opcional: Si quieres enviar también la ubicación como mensaje separado
                    if ubicacion and isinstance(ubicacion, dict) and "lat" in ubicacion and "lng" in ubicacion:
                        send_location = send_telegram_location(order_id, ubicacion["lat"], ubicacion["lng"])
                        if send_location:
                            print(f"📍 Ubicación enviada para pedido {order_id}")
                    
                    return True
                else:
                    print(f"❌ Error en respuesta de Telegram: {result}")
            else:
                print(f"❌ Error HTTP {response.status_code}: {response.text}")

            if attempt < max_retries - 1:
                wait = attempt + 2
                print(f"🔄 Reintentando en {wait} segundos...")
                time.sleep(wait)

        except Exception as e:
            print(f"❌ Excepción al enviar a Telegram: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)

    print(f"❌ No se pudo enviar el pedido {order_id} a Telegram tras {max_retries} intentos")
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
        "longitude": longitude,
        "reply_to_message_id": None,  # Se enviará como mensaje separado
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print(f"✅ Ubicación del pedido {order_id} enviada a Telegram")
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
    
    # Emojis según estado
    status_emojis = {
        "confirmado": "✅",
        "preparando": "🍕",
        "en camino": "🛵",
        "cancelado": "❌",
        "entregado": "🎉"
    }
    
    emoji = status_emojis.get(new_status, "📌")
    
    message = (
        f"{emoji} **ACTUALIZACIÓN DE PEDIDO #{order_id}**\n\n"
        f"📦 *Nuevo estado:* {new_status.upper()}\n\n"
        f"Gracias por tu paciencia 🍕"
    )
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print(f"✅ Actualización de estado {order_id} -> {new_status} enviada")
                return True
        return False
    except Exception as e:
        print(f"❌ Error enviando actualización: {e}")
        return False