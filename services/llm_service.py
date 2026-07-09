import re
import asyncio
import logging
from typing import Any
from datetime import datetime

from core.state import state
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

# Mensaje de respaldo cuando el modelo se "atora" repitiendo razonamiento
# interno (<think> sin cerrar) y no llega a producir una respuesta real
# para el cliente.
_THINK_LOOP_FALLBACK = (
    "¡Perdón! Tuve un problema procesando tu mensaje. "
    "¿Podrías repetir lo que necesitas? 🍕"
)


def strip_think_blocks(text: str) -> str:
    """
    Elimina bloques de razonamiento <think>...</think>.

    Esta función es segura de aplicar a CUALQUIER texto, incluyendo
    respuestas literales generadas en Python (LITERAL_RESPONSE_PREFIX),
    porque solo toca <think> — nunca recorta ni reordena el resto del
    mensaje. La limpieza de preámbulos/formato de salida del LLM vive
    en `strip_llm_preamble`, y esa NO debe aplicarse a texto literal.
    """
    if not text:
        return text

    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # ── FIX: bloque <think> sin cierre (modelo se quedó "enloopeado") ──
    # Si el modelo entra en un loop repitiendo su razonamiento/historial y
    # nunca llega a generar </think> (se corta por límite de tokens), el
    # regex de arriba NO hace match (falta el cierre) y el bloque crudo se
    # filtraba completo hacia el cliente. Detectamos ese caso explícito:
    # si queda un <think> abierto sin su cierre, es señal de que el modelo
    # se rompió — descartamos todo desde ahí en vez de reenviarlo.
    open_think_match = re.search(r"<think>", cleaned, re.IGNORECASE)
    if open_think_match and not re.search(r"</think>", cleaned, re.IGNORECASE):
        logger.warning(
            "strip_think_blocks: se detectó <think> sin cierre (posible loop del modelo). "
            "Se descarta el razonamiento crudo y se devuelve fallback."
        )
        cleaned = cleaned[: open_think_match.start()].strip()
        if not cleaned:
            # No quedó nada útil antes del <think> -> no hay mensaje real para el cliente.
            return _THINK_LOOP_FALLBACK

    return cleaned.strip()


def strip_llm_preamble(text: str) -> str:
    """
    Limpia preámbulos de instrucción que el LLM a veces repite antes del
    mensaje real para el cliente (ej. "El cliente respondió... reglas
    obligatorias... ¡Hola! ...").

    ⚠️ Aplicar SOLO a respuestas que efectivamente vinieron del modelo.
    NO aplicar a texto literal generado en Python (LITERAL_RESPONSE_PREFIX):
    ese texto ya está limpio, y el recorte "quedarse desde el primer
    ¡/✅/🍕" puede destruir mensajes legítimos que solo tienen un emoji
    decorativo al final (ej. "...menú completo. ¿Cuál te llama la
    atención? 🍕" quedaba reducido a solo "🍕").
    """
    if not text:
        return text

    cleaned = text

    # Quitar preámbulos de instrucción que el modelo a veces repite en la respuesta.
    patterns = [
        r"(?is)\b(?:el cliente respondió|el cliente saludó|respond[eé] con este formato exacto).*?\b(?:reglas obligatorias|reglas|formato exacto)\b\s*",
        r"(?is)\b(?:extras \(copia cada línea con • tal como aparece\):|regras obligatorias|reglas obligatorias)\b\s*",
    ]
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned)

    # Si la respuesta empieza con texto de instrucción y luego una respuesta real,
    # quedarse con la parte que parece ser el mensaje para el cliente.
    if "¡" in cleaned:
        cleaned = cleaned[cleaned.find("¡") :]
    elif "✅" in cleaned:
        cleaned = cleaned[cleaned.find("✅") :]
    elif "🍕" in cleaned:
        cleaned = cleaned[cleaned.find("🍕") :]

    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


async def generate_response(
    context: str,
    history_text: str,
    question: str,
    history: list[dict] | None = None,
) -> str:

    if history is None:
        history = []

    pizza_names = rag_service.get_pizza_names()
    extras_context = rag_service.get_available_extras_context()

    # ── LOG DIAGNÓSTICO: extras_context ─────────────────────────
    print(f"\n🧩 [LOG EXTRAS] --- DIAGNÓSTICO DE EXTRAS_CONTEXT ---")
    if extras_context:
        print(f"✅ [LOG EXTRAS] extras_context tiene {len(extras_context)} caracteres")
        print(f"📄 [LOG EXTRAS] Contenido:\n{extras_context}")
    else:
        print(f"⚠️ [LOG EXTRAS] extras_context está VACÍO o es None: {extras_context!r}")
        print(f"⚠️ [LOG EXTRAS] -> rag_service.get_available_extras_context() no devolvió nada.")

    # ── OBTENER TOTAL DEL ÚLTIMO PEDIDO (para pago) ──────────────
    total = _extract_last_total(history)
    order_id = _extract_last_order_id(history) or f"PED-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    print(f"💰 [LOG PAGO] Total del último pedido: {total}")
    print(f"📦 [LOG PAGO] Order ID: {order_id}")

    # ── DETECTAR INTENCIÓN DE PAGO DINÁMICA ──────────────────────
    payment_intent = detect_payment_intent(question)
    print(f"💳 [LOG PAGO] Intención de pago detectada: {payment_intent}")

    # ── SI EL USUARIO QUIERE CONFIRMAR UN PAGO ───────────────────
    if "confirmar pago" in question.lower() or "ya pagué" in question.lower() or "verificar pago" in question.lower():
        print(f"🔍 [LOG PAGO] Verificando pago para pedido: {order_id}")
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
            print(f"💰 [LOG PAGO] Procesando pago de ${amount} para pedido {order_id}")

            # Procesar pago con Mercado Pago o Efectivo
            payment_result = handle_payment_in_chat(
                user_id=0,  # Se puede obtener del contexto si está disponible
                order_id=order_id,
                amount=amount,
                description=f"Pedido {order_id} - {_extract_product_name(history)}",
                method=payment_intent.get("method", "mercadopago"),
                user_email=f"cliente_{order_id}@example.com",
                user_name="Cliente Pizzería 220",
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
    print(f"💳 [LOG PAGO] ¿Es pregunta de pago (legacy)? {is_payment}")

    if is_payment:
        print(f"💳 [LOG PAGO] Detectada pregunta de pago: '{question}'")
        directive = build_payment_directive(
            question=question,
            total=total,
            history=history,
        )
        print(f"📋 [LOG PAGO] Directive de pago generada:\n{directive}")
    else:
        # ── DIRECTIVA NORMAL ──────────────────────────────────────────
        directive = build_directive(
            question,
            pizza_names,
            history,
            extras_context=extras_context,
            context=context,
        )
        print(f"📋 [LOG EXTRAS] Directive generada para el LLM:\n{directive}\n")

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
            print("⚡ [LOG] Resumen final generado en Python — se omite la llamada al LLM.")
            return strip_think_blocks(directive[len(LITERAL_RESPONSE_PREFIX):])

    # ── CONSTRUIR CONTEXTO COMPLETO ──────────────────────────────
    full_context = context

    if extras_context:
        full_context += "\n\n=== INFORMACIÓN DE EXTRAS ===\n"
        full_context += extras_context
        print(f"✅ [LOG EXTRAS] Sección '=== INFORMACIÓN DE EXTRAS ===' AÑADIDA a full_context")
    else:
        print(f"🚨 [LOG EXTRAS] Sección de extras NO añadida a full_context (extras_context vacío)")

    # Si es pago, agregar información del total al contexto
    if is_payment and total:
        full_context += f"\n\n=== INFORMACIÓN DE PAGO ===\n"
        full_context += f"Total del pedido: {total}\n"
        full_context += f"Métodos de pago disponibles: Efectivo, Mercado Pago (tarjeta/QR)\n"
        full_context += f"Si el cliente pregunta por métodos de pago, ofrecelos.\n"
        full_context += f"Si el cliente quiere pagar, genera un pago con Mercado Pago.\n"
        print(f"✅ [LOG PAGO] Información de pago añadida al contexto")

    print(f"🧩 [LOG EXTRAS] --- FIN DIAGNÓSTICO ---\n")

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
    raw_response = strip_think_blocks(raw_response)
    raw_response = strip_llm_preamble(raw_response)

    # ── VALIDACIÓN POST-RESPUESTA ───────────────────────────────
    # Si la respuesta contiene precios inventados, marcarlos
    raw_response = _validate_extras_prices(raw_response, context)

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
    removidos = _extract_field(raw, "Ingredientes removidos")
    total = _extract_total(raw) or _extract_field(raw, "Total")

    parsed_extras = None
    if extras:
        parsed_extras = [item.strip() for item in re.split(r",| y ", extras) if item.strip()]

    parsed_removidos = None
    if removidos:
        parsed_removidos = [item.strip() for item in re.split(r",| y ", removidos) if item.strip()]

    return {
        "cantidad": cantidad,
        "producto": producto,
        "tamaño": tamaño,
        "extras": parsed_extras,
        "ingredientes_removidos": parsed_removidos,
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
    is_order = "📝 PEDIDO:" in content
    order_details = None

    if is_order:
        match = re.search(
            r"📝\s*PEDIDO:\s*(.*)",
            content,
            re.DOTALL,
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