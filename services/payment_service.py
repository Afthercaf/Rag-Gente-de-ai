"""
Servicio de métodos de pago para la Pizzería 220 AI.
Maneja la detección y procesamiento de métodos de pago (efectivo, Mercado Pago).

──────────────────────────────────────────────────────────────────
MÉTODOS DE PAGO SOPORTADOS:
──────────────────────────────────────────────────────────────────
1. Efectivo (Cash)
   - Cliente dice: "pago en efectivo", "efectivo", "cash"
   - Se pregunta: "¿Con cuánto vas a pagar?" y se calcula el cambio

2. Mercado Pago (Tarjeta / QR)
   - Cliente dice: "Mercado Pago", "mercado pago", "MP", "tarjeta", "QR"
   - Se genera: Total a pagar y se ofrece generar link de pago

3. Otros (por definir)
   - Transferencia bancaria, PayPal, etc.
──────────────────────────────────────────────────────────────────
"""

import re
import uuid
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from enum import Enum

# ══════════════════════════════════════════════════════════════════
# ENUMS Y DATACLASSES
# ══════════════════════════════════════════════════════════════════

class PaymentMethod(str, Enum):
    """Métodos de pago soportados."""
    CASH = "efectivo"
    MERCADO_PAGO = "mercado_pago"
    UNKNOWN = "desconocido"


@dataclass
class PaymentInfo:
    """Información del pago procesado."""
    method: PaymentMethod
    total: str  # Formato: "$XXX.XX"
    change: Optional[float] = None  # Solo para efectivo
    payment_link: Optional[str] = None  # Solo para Mercado Pago
    raw_message: str = ""


# ══════════════════════════════════════════════════════════════════
# KEYWORDS DE DETECCIÓN
# ══════════════════════════════════════════════════════════════════

CASH_KEYWORDS = {
    "efectivo", "cash", "billete", "billetes", "moneda", "monedas",
    "pago en efectivo", "pagar en efectivo", "con efectivo",
}

MERCADO_PAGO_KEYWORDS = {
    "mercado pago", "mercadopago", "mercado libre", "mercadolibre",
    "mp", "m.pago", "ml",
    "tarjeta", "tarjeta de crédito", "tarjeta de débito", "crédito", "débito",
    "qr", "código qr", "codigo qr", "escáner", "scan",
    "pago con tarjeta", "pagar con tarjeta", "con tarjeta",
    "link de pago", "link pago", "enlace de pago",
}

# Palabras que indican que el usuario está preguntando por métodos de pago
PAYMENT_QUESTION_KEYWORDS = {
    "cómo pago", "como pago", "cómo pagar", "como pagar",
    "qué métodos", "que metodos", "qué formas", "que formas",
    "cómo puedo pagar", "como puedo pagar",
    "aceptan", "reciben", "pago con", "se puede pagar",
}

# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _normalize(text: str) -> str:
    """Normaliza texto: lowercase, sin tildes, sin espacios extra."""
    import unicodedata
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _extract_amount(text: str) -> Optional[float]:
    """
    Extrae un monto en pesos del texto.
    Ejemplos: "$500", "$500.00", "500 pesos", "500 MXN", "500"
    """
    # Patrones de precio
    patterns = [
        r'\$\s*(\d+(?:[.,]\d{1,2})?)',  # $500, $500.00
        r'(\d+(?:[.,]\d{1,2})?)\s*(?:pesos?|mxn|mx|moneda nacional)',  # 500 pesos
        r'\b(\d+(?:[.,]\d{1,2})?)\s*(?:con|de)\s*efectivo',  # 500 con efectivo
        r'(\d+(?:[.,]\d{1,2})?)\s*(?:para\s+)?pagar',  # 500 para pagar
        r'^(\d+(?:[.,]\d{1,2})?)\s*$',  # Solo número
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(",", ".")
            try:
                return float(amount_str)
            except ValueError:
                continue
    return None


def _format_total(total: str) -> str:
    """Asegura que el total tenga formato consistente."""
    if not total:
        return "$0.00"
    # Si ya tiene $, mantenerlo
    if total.startswith("$"):
        return total
    # Si es un número, agregar $
    try:
        num = float(total)
        return f"${num:.2f}"
    except ValueError:
        return total


def _calculate_change(total: float, amount_paid: float) -> float:
    """Calcula el cambio (monto pagado - total)."""
    return round(amount_paid - total, 2)


# ══════════════════════════════════════════════════════════════════
# FUNCIONES PRINCIPALES
# ══════════════════════════════════════════════════════════════════

def detect_payment_method(text: str) -> Tuple[PaymentMethod, float, Optional[str]]:
    """
    Detecta el método de pago mencionado en el texto.
    
    Args:
        text: Mensaje del usuario
        
    Returns:
        Tuple[PaymentMethod, float, Optional[str]]
        - PaymentMethod: Método detectado
        - float: Monto extraído (0 si no se encuentra)
        - Optional[str]: Texto adicional (ej. "cambio" o "link")
    """
    n = _normalize(text)
    amount = _extract_amount(text) or 0.0
    
    # Detectar pregunta sobre métodos de pago
    if any(kw in n for kw in PAYMENT_QUESTION_KEYWORDS):
        return PaymentMethod.UNKNOWN, 0.0, "pregunta_metodos"
    
    # Detectar efectivo
    if any(kw in n for kw in CASH_KEYWORDS):
        return PaymentMethod.CASH, amount, "efectivo"
    
    # Detectar Mercado Pago
    if any(kw in n for kw in MERCADO_PAGO_KEYWORDS):
        return PaymentMethod.MERCADO_PAGO, amount, "mercado_pago"
    
    # Si solo hay un monto sin método específico, asumir efectivo
    if amount > 0:
        return PaymentMethod.CASH, amount, "efectivo_implícito"
    
    return PaymentMethod.UNKNOWN, 0.0, None


def process_payment(
    payment_method: PaymentMethod,
    total: str,
    amount_paid: Optional[float] = None,
) -> PaymentInfo:
    """
    Procesa el pago según el método seleccionado.
    
    Args:
        payment_method: Método de pago
        total: Total del pedido (formato "$XXX.XX")
        amount_paid: Monto pagado (solo para efectivo)
        
    Returns:
        PaymentInfo con los detalles del pago
    """
    total_formatted = _format_total(total)
    total_float = float(total_formatted.replace("$", "").replace(",", ""))
    
    info = PaymentInfo(
        method=payment_method,
        total=total_formatted,
        raw_message="",
    )
    
    if payment_method == PaymentMethod.CASH:
        if amount_paid is not None and amount_paid > 0:
            if amount_paid < total_float:
                info.change = None
                info.raw_message = (
                    f"⚠️ El monto pagado (${amount_paid:.2f}) es insuficiente. "
                    f"El total es {total_formatted}. "
                    f"¿Quieres pagar con otra cantidad o con otro método?"
                )
            else:
                change = _calculate_change(total_float, amount_paid)
                info.change = change
                info.raw_message = (
                    f"✅ Pago en efectivo por ${amount_paid:.2f}. "
                    f"Cambio: ${change:.2f}. "
                    f"¡Gracias por tu compra! 🍕"
                )
        else:
            info.raw_message = (
                f"💰 Has seleccionado pago en efectivo. "
                f"El total es {total_formatted}. "
                f"¿Con cuánto vas a pagar?"
            )
    
    elif payment_method == PaymentMethod.MERCADO_PAGO:
        id_generado = uuid.uuid4().hex[:12]
        info.payment_link = f"https://link.mercadopago.com/pizzeria220/{id_generado}"
        info.raw_message = (
            f"💳 Has seleccionado Mercado Pago. "
            f"El total es {total_formatted}. "
            f"Te enviaré un enlace de pago por este monto.\n"
            f"📲 Enlace: [link de pago]\n"
            f"¿Confirmas el pago con Mercado Pago?"
        )
    
    else:
        info.raw_message = (
            f"📋 No he podido identificar el método de pago. "
            f"Los métodos disponibles son:\n"
            f"  • Efectivo (pago en persona)\n"
            f"  • Mercado Pago (tarjeta / QR)\n"
            f"¿Cuál prefieres? 🍕"
        )
    
    return info


def build_payment_directive(
    question: str,
    total: str,
    history: list[dict],
) -> str:
    """
    Genera una directiva para el LLM sobre cómo manejar la pregunta
    de pago del usuario.
    
    Args:
        question: Mensaje del usuario
        total: Total del pedido
        history: Historial de conversación
        
    Returns:
        Directive para el LLM
    """
    n = _normalize(question)
    
    # Detectar método de pago
    method, amount, _ = detect_payment_method(question)
    total_formatted = _format_total(total)
    
    # Si es una pregunta sobre métodos de pago
    if any(kw in n for kw in PAYMENT_QUESTION_KEYWORDS):
        return (
            f"El cliente preguntó sobre métodos de pago. "
            f"El total de su pedido es {total_formatted}. "
            f"Responde EXACTAMENTE con este formato:\n\n"
            f"📋 **Métodos de pago disponibles:**\n\n"
            f"💰 **Efectivo:** Pago en persona. Puedes pagar con billetes o monedas.\n"
            f"  • ¿Con cuánto vas a pagar? Te daré el cambio exacto.\n\n"
            f"💳 **Mercado Pago:** Pago con tarjeta o código QR.\n"
            f"  • Te enviaré un enlace de pago por el total.\n"
            f"  • Aceptamos tarjetas de crédito, débito y Mercado Pago.\n\n"
            f"¿Qué método prefieres? 🍕"
        )
    
    # Si es efectivo
    if method == PaymentMethod.CASH:
        if amount > 0:
            return (
                f"El cliente quiere pagar en efectivo con ${amount:.2f}. "
                f"El total del pedido es {total_formatted}. "
                f"Calcula el cambio y responde amablemente. "
                f"Si el pago es insuficiente, avísale y pregúntale si quiere pagar con otra cantidad."
            )
        else:
            return (
                f"El cliente quiere pagar en efectivo pero no especificó el monto. "
                f"El total del pedido es {total_formatted}. "
                f"Pregunta: '¿Con cuánto vas a pagar? 💰'"
            )
    
    # Si es Mercado Pago
    if method == PaymentMethod.MERCADO_PAGO:
        return (
            f"El cliente quiere pagar con Mercado Pago. "
            f"El total del pedido es {total_formatted}. "
            f"Confirma el método y pregunta si desea el link de pago.\n"
            f"Responde como: 'Perfecto, te enviaré el link de pago por {total_formatted} a través de Mercado Pago. ¿Confirmas? 💳'"
        )
    
    # Si no se detectó método, preguntar
    return (
        f"El cliente quiere saber cómo pagar pero no especificó el método. "
        f"El total del pedido es {total_formatted}. "
        f"Responde EXACTAMENTE con este formato:\n\n"
        f"📋 **Métodos de pago disponibles:**\n\n"
        f"💰 **Efectivo:** Pago en persona.\n"
        f"💳 **Mercado Pago:** Pago con tarjeta o QR.\n\n"
        f"¿Cuál prefieres? 🍕"
    )


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN PARA INTEGRAR CON EL FLUJO DE PEDIDO
# ══════════════════════════════════════════════════════════════════

def is_payment_question(text: str) -> bool:
    """
    Detecta si el mensaje del usuario está relacionado con el pago.
    """
    n = _normalize(text)
    
    # Keywords de pago
    payment_keywords = {
        "pago", "pagar", "cómo pago", "como pago", "método", "metodo",
        "efectivo", "mercado", "mercado libre", "mercadolibre", "tarjeta",
        "qr", "cambio", "vuelto",
    }
    
    return any(kw in n for kw in payment_keywords)


def extract_payment_info(text: str) -> Dict[str, Any]:
    """
    Extrae toda la información de pago de un mensaje.
    
    Returns:
        Dict con: method, amount, change_request, etc.
    """
    n = _normalize(text)
    amount = _extract_amount(text)
    
    # Detectar si pide cambio
    change_request = any(kw in n for kw in ["cambio", "vuelto", "cambió", "vuelta"])
    
    # Detectar método
    method, _, method_detail = detect_payment_method(text)
    
    return {
        "method": method.value,
        "method_detail": method_detail,
        "amount": amount,
        "change_request": change_request,
        "raw": text,
    }