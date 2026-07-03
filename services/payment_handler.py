"""
Manejador de pagos para el chat - Integración dinámica
"""

import re
from typing import Optional, Tuple, Dict, Any
from datetime import datetime

from services.mercadopago_service import (
    mercadopago_service,
    PaymentResult,
    PaymentLink,
    PaymentStatus,
)


def detect_payment_intent(text: str) -> Dict[str, Any]:
    """
    Detecta la intención de pago del usuario en el chat
    
    Returns:
        Dict con: method, amount, order_id, action
    """
    text_lower = text.lower()
    result = {
        "is_payment": False,
        "method": None,
        "amount": None,
        "order_id": None,
        "action": None,
    }

    # Detectar si quiere pagar
    payment_keywords = ["pagar", "pago", "paga", "efectivo", "mercado pago", "tarjeta"]
    if not any(kw in text_lower for kw in payment_keywords):
        return result

    result["is_payment"] = True

    # Detectar método de pago
    if "mercado pago" in text_lower or "tarjeta" in text_lower or "qr" in text_lower:
        result["method"] = "mercadopago"
        result["action"] = "create_payment"
    elif "efectivo" in text_lower or "cash" in text_lower:
        result["method"] = "cash"
        result["action"] = "cash_payment"

    # Extraer monto
    amount_match = re.search(r'(\d+(?:\.\d{1,2})?)', text)
    if amount_match:
        result["amount"] = float(amount_match.group(1))

    # Extraer ID de pedido
    order_match = re.search(r'pedido\s*[#:]?\s*([A-Z0-9]+)', text, re.IGNORECASE)
    if order_match:
        result["order_id"] = order_match.group(1)

    return result


def handle_payment_in_chat(
    user_id: int,
    order_id: str,
    amount: float,
    description: str,
    method: str = "mercadopago",
    user_email: str = None,
    user_name: str = None,
) -> Dict[str, Any]:
    """
    Procesa un pago desde el chat de forma dinámica
    
    Returns:
        Dict con la respuesta para el chat
    """
    # Crear sesión de pago
    session = mercadopago_service.create_payment_session(
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        description=description,
        user_email=user_email,
        user_name=user_name,
    )

    if method == "mercadopago":
        # Crear pago en Mercado Pago
        payment = mercadopago_service.create_payment(
            amount=amount,
            description=description,
            order_id=order_id,
            user_email=user_email or "cliente@example.com",
            user_name=user_name or "Cliente",
        )

        if payment.success:
            # Generar respuesta con QR o link
            return {
                "success": True,
                "method": "mercadopago",
                "payment_id": payment.payment_id,
                "status": payment.status,
                "qr_code": payment.qr_code,
                "qr_code_base64": payment.qr_code_base64,
                "ticket_url": payment.ticket_url,
                "message": _format_payment_response(payment, session),
                "session": session,
            }
        else:
            return {
                "success": False,
                "error": payment.error_message,
                "message": f"❌ No se pudo crear el pago: {payment.error_message}",
            }

    elif method == "cash":
        return {
            "success": True,
            "method": "cash",
            "message": f"""
💰 **Pago en efectivo - Pedido {order_id}**
Monto: ${amount:.2f}

Por favor acércate al local para pagar en efectivo.
¿Con cuánto vas a pagar? Te daré el cambio exacto.
""",
            "session": session,
        }

    return {
        "success": False,
        "error": "Método de pago no soportado",
    }


def _format_payment_response(payment: PaymentResult, session) -> str:
    """Formatea la respuesta para el chat"""
    is_test = "🔬 [MODO PRUEBA] " if payment.is_test else ""

    if payment.qr_code:
        qr_message = f"📱 **Código QR:**\n```\n{payment.qr_code[:100]}...\n```"
    else:
        qr_message = ""

    return f"""
{is_test}💰 **Pago creado - Pedido {session.order_id}**

Monto: ${payment.transaction_amount:.2f}
Estado: {payment.status}
ID de pago: {payment.payment_id}

{qr_message}

📲 **Opciones de pago:**
1. Escanea el código QR
2. Usa el link de pago: {payment.ticket_url or "Link disponible en el local"}

⏰ Tienes 30 minutos para completar el pago.

¿Ya realizaste el pago? Escribe "confirmar pago" para verificarlo.
"""


def confirm_payment(order_id: str) -> Dict[str, Any]:
    """
    Confirma un pago verificando su estado
    """
    result = mercadopago_service.check_and_update_session(order_id)

    if result:
        if result["status"] == "approved":
            return {
                "success": True,
                "confirmed": True,
                "message": f"✅ ¡Pago confirmado! Pedido {order_id} completado. ¡Gracias por tu compra! 🍕",
                "payment": result,
            }
        elif result["status"] == "pending":
            return {
                "success": True,
                "confirmed": False,
                "message": f"⏳ El pago del pedido {order_id} aún está pendiente. Por favor espera un momento.",
                "payment": result,
            }
        elif result["status"] == "rejected":
            return {
                "success": True,
                "confirmed": False,
                "message": f"❌ El pago fue rechazado. Por favor intenta nuevamente.",
                "payment": result,
            }

    return {
        "success": False,
        "confirmed": False,
        "message": "No se encontró un pago activo para este pedido.",
    }


def get_payment_status_message(order_id: str) -> str:
    """Obtiene el mensaje de estado de pago para el chat"""
    session = mercadopago_service.get_session(order_id)
    if not session:
        return "No hay un pago activo para este pedido."

    return mercadopago_service.get_active_session_message(order_id)