import re
import asyncio
import logging
from typing import Any
from datetime import datetime

from core.state import state
from core.prompt_guard import contains_system_prompt_fragment
from services import rag_service
from services.intent_detector import build_directive, LITERAL_RESPONSE_PREFIX
from services.payment_service import (
    is_payment_question,
    build_payment_directive,
    PaymentMethod,
    process_payment,
    detect_payment_method,
)

# ── NUEVAS IMPORTACIONES PARA PAGO DINÁMICO ──────────────────────
from services.mercadopago_service import mercadopago_service
from services.payment_handler import (
    handle_payment_in_chat,
    confirm_payment,
    get_payment_status_message,
    detect_payment_intent,
)

logger = logging.getLogger(__name__)


def _normalize_reference_text(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", str(value or "").lower())
    normalized = "".join(
        char for char in normalized
        if not unicodedata.combining(char)
    )
    return re.sub(r"\s+", " ", normalized).strip()


def _resolve_contextual_pizza_question(
    question: str,
    history: list[dict],
    pizza_names: list[str],
) -> str:
    """Convierte referencias como ``esa pizza`` en un pedido explícito.

    Ejemplo:
        Historial: "La Pizza Margarita lleva..."
        Pregunta: "¿Me puede dar esa pizza?"
        Resultado: "Quiero una Pizza Margarita"

    Esta resolución ocurre antes de build_directive para que el flujo normal
    cree y persista el carrito del usuario.
    """
    normalized = _normalize_reference_text(question)

    order_reference = bool(re.search(
        r"\b(?:"
        r"me\s+puede(?:s)?\s+dar|"
        r"me\s+das|"
        r"dame|"
        r"quiero|"
        r"quisiera|"
        r"me\s+gustaria|"
        r"pedir|"
        r"ordenar"
        r")\b",
        normalized,
    )) and bool(re.search(
        r"\b(?:esa|esta|la\s+misma)(?:\s+pizza)?\b",
        normalized,
    ))

    if not order_reference:
        return question

    # El historial de session_service guarda cada intercambio como:
    # {"user": "...", "assistant": "..."}.
    # También aceptamos otros formatos para mantener compatibilidad.
    for message in reversed(history[-12:]):
        if not isinstance(message, dict):
            continue

        contents = [
            message.get("assistant"),
            message.get("user"),
            message.get("content"),
            message.get("text"),
            message.get("message"),
        ]

        for raw_content in contents:
            if not raw_content:
                continue

            normalized_content = _normalize_reference_text(raw_content)

            # Preferir nombres más largos para evitar coincidencias parciales.
            for pizza_name in sorted(pizza_names, key=len, reverse=True):
                clean_name = re.sub(
                    r"^pizza\s+",
                    "",
                    _normalize_reference_text(pizza_name),
                ).strip()

                if not clean_name:
                    continue

                if re.search(
                    rf"\b(?:pizza\s+)?{re.escape(clean_name)}\b",
                    normalized_content,
                ):
                    display_name = re.sub(
                        r"^pizza\s+",
                        "",
                        str(pizza_name),
                        flags=re.IGNORECASE,
                    ).strip()

                    logger.debug("Referencia contextual de pizza resuelta")
                    return f"Quiero una Pizza {display_name}"

    return question


async def generate_response(
    context: str,
    history_text: str,
    question: str,
    history: list[dict] | None = None,
    *,
    session: dict | None = None,
    user_id: int = 0,
) -> str:

    if history is None:
        history = []

    pizza_names = rag_service.get_pizza_names()

    # Resolver "esa pizza" usando la conversación previa antes de detectar
    # intención, productos y precios.
    question = _resolve_contextual_pizza_question(
        question,
        history,
        pizza_names,
    )

    extras_context = rag_service.get_available_extras_context()
    promos_text = rag_service.get_promos_text()

    # Estado aislado del carrito por usuario. La sesión debe venir de
    # get_user_session(user_id) en chat.py.
    current_cart = None
    last_order = None
    if session is not None:
        from services.session_service import get_current_cart, get_last_order, set_current_cart
        current_cart = get_current_cart(session, user_id)
        if current_cart is None:
            current_cart = {
                "user_id": user_id, "status": "idle", "cursor": 0,
                "items": [], "observations": [],
            }
            set_current_cart(session, user_id, current_cart)
        last_order = get_last_order(session, user_id)
    best_seller = rag_service.get_best_seller()

    logger.debug("Contexto de extras disponible=%s", bool(extras_context))

    # ── OBTENER TOTAL DEL ÚLTIMO PEDIDO (para pago) ──────────────
    total = _extract_last_total(history)
    order_id = _extract_last_order_id(history) or f"PED-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # ── ESTADO DE PAGO EN EFECTIVO CONTROLADO POR SESIÓN ─────────
    # Mercado Pago se conserva como opción final; el flujo en efectivo se
    # resuelve aquí para que una cantidad como "1200" no caiga al fallback.
    wants_to_fix_extras = bool(re.search(
        r"\b(?:extra|extras|falto|falta|faltan|agrega|agregar|añade|anade)\b",
        question.strip().lower(),
    ))
    pending_checkout = bool(
        current_cart
        and current_cart.get("status") in {"awaiting_payment", "awaiting_location"}
    )
    normalized_checkout_question = _normalize_reference_text(question)

    if (
        pending_checkout
        and re.search(
            r"\b(?:cancelar|cancela|no quiero|ya no quiero|olvida el pedido)\b",
            normalized_checkout_question,
        )
    ):
        current_cart.clear()
        current_cart.update({
            "status": "cancelled",
            "items": [],
            "cursor": 0,
            "user_id": user_id,
        })
        return "✅ Pedido pendiente cancelado. Puedes iniciar uno nuevo cuando quieras."

    if (
        pending_checkout
        and wants_to_fix_extras
    ):
        current_cart["status"] = "collecting_extras"
        current_cart["cursor"] = 0
        current_cart.pop("payment_method", None)
        return (
            "Claro, todavía puedes corregir los extras antes de enviar el pedido.\n\n"
            f"{extras_context}\n\n"
            "Escribe los extras que deseas agregar o responde “ninguno”."
        )

    if (
        pending_checkout
        and normalized_checkout_question
        in {"hola", "buenas", "buenos dias", "buenas tardes", "buenas noches"}
    ):
        pizzas = ", ".join(
            str(item.get("pizza") or "Pizza")
            for item in current_cart.get("items", [])
        )
        return (
            f"¡Hola! 🍕 Tienes un pedido pendiente: {pizzas}.\n\n"
            "Puedes escribir:\n"
            "• continuar\n"
            "• faltan mis extras\n"
            "• cancelar pedido"
        )

    if current_cart and current_cart.get("status") == "awaiting_payment":
        qn = question.strip().lower()

        if "efectivo" in qn:
            current_cart["status"] = "awaiting_location"
            current_cart["payment_method"] = "efectivo"
            return (
                "📍 Para completar tu pedido, necesito tu ubicación exacta.\n"
                "📍 Compartir mi ubicación"
            )

        if "mercado pago" in qn or "mercadopago" in qn:
            current_cart["payment_method"] = "mercado_pago"
            # El procesamiento existente de Mercado Pago continúa debajo.
        else:
            return (
                "💳 ¿Cómo deseas pagar?\n"
                "• Efectivo\n"
                "• Mercado Pago"
            )

    if current_cart and current_cart.get("status") == "awaiting_location":
        return (
            "📍 Para completar tu pedido, comparte tu ubicación exacta.\n"
            "📍 Compartir mi ubicación"
        )

    # ── DETECTAR INTENCIÓN DE PAGO DINÁMICA ──────────────────────
    payment_intent = detect_payment_intent(question)
    logger.debug("Intención de pago detectada=%s", payment_intent["is_payment"])

    # ── SI EL USUARIO QUIERE CONFIRMAR UN PAGO ───────────────────
    if "confirmar pago" in question.lower() or "ya pagué" in question.lower() or "verificar pago" in question.lower():
        logger.info("Verificando estado de pago")
        confirm_result = confirm_payment(order_id)
        if confirm_result["success"] and confirm_result.get("confirmed"):
            return confirm_result["message"]
        elif confirm_result["success"]:
            status_msg = get_payment_status_message(order_id)
            return status_msg
        else:
            return "No encontré un pago pendiente para tu pedido. ¿Quieres iniciar uno nuevo?"

    # ── PROCESAR PAGO SI EL USUARIO QUIERE PAGAR ────────────────
    if payment_intent["is_payment"] and total:
        amount = payment_intent.get("amount") or _extract_amount(total)
        if amount and amount > 0:
            logger.info("Procesando pago validado por el servidor")

            # Procesar pago con Mercado Pago o Efectivo
            # VULN-03: evitar datos de ejemplo; usar valores mínimos anonimizados.
            payment_result = handle_payment_in_chat(
                user_id=user_id,
                order_id=order_id,
                amount=amount,
                description=f"Pedido {order_id} - {_extract_product_name(history)}",
                method=payment_intent.get("method", "mercadopago"),
                user_email=f"pedido-{order_id}@anonimo.local",
                user_name="Cliente",
            )

            if payment_result["success"]:
                return payment_result["message"]
            else:
                return f"❌ Error al procesar el pago: {payment_result.get('error', 'Intenta nuevamente')}"

    # ── SI EL USUARIO PREGUNTA POR EL ESTADO DEL PAGO ───────────
    if "estado del pago" in question.lower() or "cómo va mi pago" in question.lower():
        status_msg = get_payment_status_message(order_id)
        return status_msg

    # ── SI EL USUARIO QUIERE VER LOS MÉTODOS DE PAGO ────────────
    if "métodos de pago" in question.lower() or "cómo puedo pagar" in question.lower() or "formas de pago" in question.lower():
        return f"""
📋 **Métodos de pago disponibles en Pizzería 220:**

💰 **Efectivo** - Pago en persona en el local
   - ¿Con cuánto vas a pagar? Te daré el cambio exacto.

💳 **Mercado Pago** - Pago con tarjeta o código QR
   - Te genero un link de pago o código QR instantáneo.
   - Acepta tarjetas de crédito, débito y Mercado Pago.

📲 **Para pagar con Mercado Pago:**
1. Escribe **"quiero pagar con Mercado Pago"**
2. Te daré un código QR o link de pago
3. Escanea el QR o da click en el link para completar el pago
4. Una vez pagado, escribe **"confirmar pago"**

Total a pagar: **{total if total else "Consultando..."}**

¿Cómo deseas pagar?
"""

    # ── DETECTAR PREGUNTA DE PAGO (legacy) ──────────────────────
    is_payment = total and is_payment_question(question)
    logger.debug("Pregunta de pago=%s", bool(is_payment))

    if is_payment:
        directive = build_payment_directive(
            question=question,
            total=total,
            history=history,
        )
    else:
        # ── DIRECTIVA NORMAL ──────────────────────────────────────────
        directive = build_directive(
            question,
            pizza_names,
            history,
            extras_context=extras_context,
            context=context,
            promos_text=promos_text,
            current_cart=current_cart,
            best_seller=best_seller,
            last_order=last_order,
            user_id=user_id,
        )

        # ── FIX: resumen final 100% literal, sin pasar por el LLM ────
        # build_directive() marca con LITERAL_RESPONSE_PREFIX los casos
        # donde el texto ya viene completamente armado en Python (ej.
        # el resumen final del pedido, con Producto/Total ya
        # calculados). Antes ese texto se le pasaba al LLM como
        # "instrucción para copiar literal", pero seguía siendo el LLM
        # quien redactaba la respuesta final — sin garantía real de que
        # no alterara esos valores (se observó un caso donde el resumen
        # mostró la pizza/total de un pedido anterior ya confirmado en
        # vez del pedido recién armado). Si el prefijo está presente,
        # se devuelve el texto directo, sin invocar al modelo.
        if directive.startswith(LITERAL_RESPONSE_PREFIX):
            logger.debug("Respuesta literal generada sin invocar al modelo")
            return directive[len(LITERAL_RESPONSE_PREFIX):]

    # ── CONSTRUIR CONTEXTO COMPLETO ──────────────────────────────
    full_context = context

    if extras_context:
        full_context += "\n\n=== INFORMACIÓN DE EXTRAS ===\n"
        full_context += extras_context

    # Si es pago, agregar información del total al contexto
    if is_payment and total:
        full_context += f"\n\n=== INFORMACIÓN DE PAGO ===\n"
        full_context += f"Total del pedido: {total}\n"
        full_context += f"Métodos de pago disponibles: Efectivo, Mercado Pago (tarjeta/QR)\n"
        full_context += f"Si el cliente pregunta por métodos de pago, ofrecelos.\n"
        full_context += f"Si el cliente quiere pagar, genera un pago con Mercado Pago.\n"

    # ── GENERAR PROMPT Y LLAMAR AL MODELO ─────────────────────────
    prompt = state["prompt_template"].format_messages(
        context=full_context,
        history=history_text,
        question=question,
        directive=directive,
    )
    model = state["model_loader"].model
    state["model_loaded"] = True

    response = await asyncio.to_thread(
        model.invoke,
        prompt,
        stop=[
            "PREGUNTA DEL CLIENTE:",
            "RESPUESTA:",
            "👤 Usuario:",
            "<historial_conversacion>",
            "📝 PEDIDOS:"
        ]
    )

    raw_response = response.content.strip()

    # Bloqueo de fuga de prompt/información interna y respuestas absurdas.
    leak_markers = (
        "system prompt", "developer message", "estructura de tu base de datos",
        "<historial_conversacion>", "instrucciones internas", "```python",
        "print(\"hola, mundo", "print('hola, mundo",
    )
    normalized_output = raw_response.lower()
    if (
        any(marker in normalized_output for marker in leak_markers)
        or contains_system_prompt_fragment(raw_response)
    ):
        return (
            "No puedo proporcionar información interna del sistema. "
            "Puedo ayudarte con el menú, precios o un pedido."
        )

    # ── VALIDACIÓN POST-RESPUESTA ───────────────────────────────
    # Si la respuesta contiene precios inventados, marcarlos
    raw_response = _validate_extras_prices(raw_response, full_context)

    # ── PROCESAR RESPUESTA DE PAGO (si aplica) ──────────────────
    if is_payment and total:
        raw_response = _process_payment_response(raw_response, question, total, history)

    return raw_response


def _extract_last_total(history: list[dict]) -> str:
    """
    Extrae el total del último pedido confirmado en el historial.
    """
    for msg in reversed(history):
        assistant_msg = msg.get("assistant", "")
        if "📝 PEDIDO:" in assistant_msg:
            # Buscar el total en el pedido
            match = re.search(
                r"(?:Total|Importe|Monto)\s*[:=]\s*([^\n]+)",
                assistant_msg,
                re.IGNORECASE,
            )
            if match:
                total = match.group(1).strip()
                # Limpiar formato
                total = re.sub(r'[^$\d.,]', '', total)
                if total:
                    return total
    return ""


def _extract_last_order_id(history: list[dict]) -> str | None:
    """
    Extrae el ID del último pedido del historial.
    """
    for msg in reversed(history):
        assistant_msg = msg.get("assistant", "")
        if "📝 PEDIDO:" in assistant_msg:
            # Buscar ID de pedido
            match = re.search(r"Pedido\s*[#:]?\s*([A-Z0-9-]+)", assistant_msg, re.IGNORECASE)
            if match:
                return match.group(1)
            # Si no hay ID explícito, generar uno basado en timestamp
            match = re.search(r"(\d{8,14})", assistant_msg)
            if match:
                return f"PED-{match.group(1)}"
    return None


def _extract_product_name(history: list[dict]) -> str:
    """
    Extrae el nombre del producto del último pedido.
    """
    for msg in reversed(history):
        assistant_msg = msg.get("assistant", "")
        if "📝 PEDIDO:" in assistant_msg:
            match = re.search(r"Producto\s*[:=]\s*([^\n]+)", assistant_msg, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return "Pizza"


def _extract_amount(total_str: str) -> float:
    """
    Extrae el monto numérico de un string de total.
    """
    try:
        return float(re.sub(r'[^0-9.]', '', total_str))
    except:
        return 0.0


def _process_payment_response(
    response: str,
    question: str,
    total: str,
    history: list[dict],
) -> str:
    """
    Procesa la respuesta del asistente para detectar y manejar información de pago.
    """
    # Detectar si el usuario mencionó un método de pago en su pregunta
    method, amount, _ = detect_payment_method(question)

    # Si el usuario mencionó efectivo con un monto
    if method == PaymentMethod.CASH and amount > 0:
        payment_info = process_payment(
            payment_method=PaymentMethod.CASH,
            total=total,
            amount_paid=amount,
        )
        # Si el pago es suficiente, agregar confirmación
        if payment_info.change is not None:
            return f"{response}\n\n{payment_info.raw_message}"
        elif payment_info.change is None and amount > 0:
            # Pago insuficiente
            return f"{response}\n\n{payment_info.raw_message}"
        else:
            return response

    # Si el usuario mencionó Mercado Pago
    if method == PaymentMethod.MERCADO_PAGO:
        payment_info = process_payment(
            payment_method=PaymentMethod.MERCADO_PAGO,
            total=total,
        )
        # Agregar información de Mercado Pago a la respuesta
        return f"{response}\n\n{payment_info.raw_message}"

    return response


def _validate_extras_prices(response: str, full_context: str) -> str:
    """
    Valida que los precios mencionados en la respuesta existan en el contexto.
    Si no, los elimina o los marca.
    """
    # Extraer todos los precios de la respuesta
    price_pattern = r'\$\s*(\d+(?:\.\d{2})?)'
    response_prices = re.findall(price_pattern, response)
    
    if not response_prices:
        return response
    
    # Extraer precios válidos del contexto
    valid_prices = re.findall(price_pattern, full_context)
    valid_prices_set = set(valid_prices)
    
    # Si hay precios en la respuesta que no están en el contexto
    invalid_prices = [p for p in response_prices if p not in valid_prices_set]
    
    if invalid_prices:
        # Opción 1: Eliminar líneas con precios inválidos
        lines = response.split('\n')
        cleaned_lines = []
        for line in lines:
            # Si la línea tiene un precio inválido, omitirla o reemplazarla
            for price in invalid_prices:
                if f'${price}' in line or f'$ {price}' in line:
                    line = line.replace(f'${price}', '[precio no disponible]')
                    line = line.replace(f'$ {price}', '[precio no disponible]')
            cleaned_lines.append(line)
        response = '\n'.join(cleaned_lines)
    
    return response


def _extract_field(raw: str, name: str) -> str | None:
    """Extrae un campo del formato 'Nombre: valor'."""
    pattern = rf"(?im)^{re.escape(name)}\s*:\s*(.*?)(?=\n^[A-ZÁÉÍÓÚÑ][^\n]*?:|\Z)"
    match = re.search(pattern, raw, re.DOTALL | re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_total(raw: str) -> str | None:
    """Extrae el total de un texto."""
    # Primera opción: campo explícito Total/Importe/Monto
    match = re.search(
        r"(?im)^(?:total|importe|precio total|monto|subtotal)\s*[:=-]?\s*(?:\$|usd|mxn)?\s*([0-9]+(?:[.,][0-9]{1,2})?)\b",
        raw,
        re.MULTILINE,
    )
    if match:
        return match.group(1).replace(",", ".")

    # Segunda opción: línea de precio genérico con símbolo
    match = re.search(
        r"(?im)^(?:precio|costo|valor)\s*[:=-]?\s*(?:\$|usd|mxn)?\s*([0-9]+(?:[.,][0-9]{1,2})?)\b",
        raw,
        re.MULTILINE,
    )
    if match:
        return match.group(1).replace(",", ".")

    return None


def _parse_order_section(raw: str) -> dict[str, Any]:
    """Parsea la sección de pedido."""
    cantidad = _extract_field(raw, "Cantidad")
    producto = _extract_field(raw, "Producto")
    tamaño = _extract_field(raw, "Tamaño")
    extras = _extract_field(raw, "Extras")
    observaciones = _extract_field(raw, "Observaciones")
    total = _extract_total(raw) or _extract_field(raw, "Total")
    products_block = _extract_field(raw, "Productos")

    products = []
    if products_block:
        for line in products_block.splitlines():
            match = re.search(
                r"^\s*[^\d]*?(\d+)\s*(?:x|×)\s*Pizza\s+(.+?)(?:\s+(?:—|-)\s+|\s*$)",
                line,
                re.IGNORECASE,
            )
            if match:
                products.append({"cantidad": int(match.group(1)), "producto": match.group(2).strip()})
        if products and not producto:
            producto = ", ".join(
                f"{item['cantidad']} Pizza {item['producto']}" for item in products
            )
        if products and not cantidad:
            cantidad = str(sum(item["cantidad"] for item in products))

    parsed_extras = None
    if extras:
        parsed_extras = [item.strip() for item in re.split(r",| y ", extras) if item.strip()]

    return {
        "cantidad": cantidad,
        "producto": producto,
        "productos": products or None,
        "tamaño": tamaño,
        "extras": parsed_extras,
        "observaciones": observaciones,
        "total": total,
    }


def extract_order_details(content: str) -> tuple[bool, dict[str, Any] | None]:
    """
    Extrae los detalles de un pedido del contenido de la respuesta del asistente.
    
    Args:
        content: El contenido de la respuesta del asistente.
        
    Returns:
        tuple[bool, dict | None]: (is_order, order_details)
    """
    is_order = bool(re.search(r"(?m)^\s*(?:\W+\s*)?PEDIDO:\s*", content))
    order_details = None

    if is_order:
        match = re.search(
            r"(?ms)^\s*(?:\W+\s*)?PEDIDO:\s*(.*)",
            content,
        )

        if match:
            raw = match.group(1).strip()
            raw = re.split(r"\n\s*(?:PROMOCIONES:|PEDIDOS:)\b", raw, maxsplit=1)[0].strip()
            parsed = _parse_order_section(raw)
            parsed["raw"] = raw
            order_details = parsed

    return is_order, order_details


def extract_confirmation_status(content: str) -> bool:
    """
    Detecta si el usuario ha confirmado un pedido.
    """
    confirmation_patterns = [
        r"si\s*[,.]?\s*(?:confirmo|confirmar|está? bien|perfecto)",
        r"(?:confirmo|confirmar)\s*[,.]?\s*(?:si|está? bien|perfecto)",
        r"lo\s+confirmo",
        r"confirmo\s+mi\s+pedido",
        r"✅",
        r"está?\s+bien\s*[,.]?\s*(?:confirmo|confirmar)?",
        r"perfecto\s*[,.]?\s*(?:confirmo|confirmar)?",
        r"listo\s*[,.]?\s*(?:confirmo|confirmar)?",
        r"dale",
        r"ok",
        r"si",
    ]
    
    content_lower = content.lower()
    for pattern in confirmation_patterns:
        if re.search(pattern, content_lower):
            return True
    return False


# ══════════════════════════════════════════════════════════════════
# FUNCIONES PARA EXTRACCIÓN DE INFORMACIÓN DE PAGO
# ══════════════════════════════════════════════════════════════════

def extract_payment_info_from_response(response: str) -> dict[str, Any]:
    """
    Extrae información de pago de la respuesta del asistente.
    """
    info = {
        "has_payment": False,
        "method": None,
        "total": None,
        "change": None,
        "payment_link": None,
        "needs_follow_up": False,
    }

    # Detectar si hay información de pago
    if "efectivo" in response.lower() or "mercado pago" in response.lower():
        info["has_payment"] = True

    # Extraer total
    total_match = re.search(r"(?:Total|Importe)\s*[:=]\s*([^\n]+)", response, re.IGNORECASE)
    if total_match:
        info["total"] = total_match.group(1).strip()

    # Extraer cambio (para efectivo)
    change_match = re.search(r"Cambio\s*[:=]\s*([^\n]+)", response, re.IGNORECASE)
    if change_match:
        info["change"] = change_match.group(1).strip()

    # Detectar método
    if "efectivo" in response.lower():
        info["method"] = "efectivo"
    elif "mercado pago" in response.lower():
        info["method"] = "mercado_pago"
    elif "tarjeta" in response.lower():
        info["method"] = "mercado_pago"

    # Detectar si necesita seguimiento
    if "¿con cuánto" in response.lower() or "¿cuánto" in response.lower():
        info["needs_follow_up"] = True

    return info


# ══════════════════════════════════════════════════════════════════
# FUNCIÓN DE UTILIDAD PARA EL CHAT - OBTENER ESTADO DE PAGO
# ══════════════════════════════════════════════════════════════════

def get_payment_status_for_chat(order_id: str) -> str:
    """
    Función de utilidad para obtener el estado de pago desde el chat.
    """
    return get_payment_status_message(order_id)
