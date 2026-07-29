import re
import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from core.cache import response_cache
from core.decorators import measure_time
from core.state import state
from pydantic import BaseModel, ConfigDict, Field
from core.security import CurrentUser, get_current_user
from services import llm_service, rag_service
from services.intent_detector import (
    has_order_intent,
    has_pizza_name,
    is_order_flow_active,
    is_prompt_injection,
)
from services.session_service import (
    append_to_history,
    build_enriched_query,
    build_history_text,
    get_user_session,
    get_last_order,
    set_last_order,
    clear_last_order,
    LastOrder,
)
from src.supabase_chat import delete_chat_history, get_chat_history
from utils.cache_keys import get_cache_key

logger = logging.getLogger(__name__)


# ── Frases que indican "repetir mi último pedido" (BUG 1) ──────────────
REPEAT_PHRASES = [
    "lo de siempre", "lo mismo", "la misma", "la misma pizza",
    "el mismo pedido", "el anterior", "la anterior",
    "repite mi pedido", "vuelve a pedir", "vuelve a pedir lo mismo",
    "igual que hace rato", "igual que la ultima", "igual que la última",
    "el pedido anterior", "repetir pedido", "otra igual", "otra igualita",
    "quiero la de siempre", "pido lo de siempre",
]


def _is_repeat_phrase(query: str) -> bool:
    text = query.lower()
    return any(phrase in text for phrase in REPEAT_PHRASES)


# ── Detección de saludo simple (para bienvenida, BUG 5) ───────────────
_SALUDO_RE = re.compile(
    r"\b(hola|buenas|buenos dias|buenas tardes|buenas noches|hey|saludos|qué tal|que tal)\b",
    re.IGNORECASE,
)


def is_new_order_query(query: str, pizza_names: list[str]) -> bool:
    text = query.lower()
    has_order_intent = bool(re.search(
        r"\b(quiero|quisiera|me gustaria|me gustaría|dame|ordenar|pedir|trae|me das)\b",
        text,
    ))
    has_pizza_reference = bool(re.search(r"\bpiz{1,2}a\b", text)) or any(
        name.lower() in text for name in pizza_names
    )
    return has_order_intent and has_pizza_reference


_ACTIVE_CART_STATUSES = {
    "asking_any_extras",
    "collecting_extras",
    "awaiting_confirmation",
    "awaiting_payment",
    "awaiting_location",
    "awaiting_payment_method",
    "awaiting_cash_amount",
}


def _get_cart_status(session: dict) -> str:
    cart = session.get("current_cart") or {}
    return str(cart.get("status") or "").strip().lower()


def _is_session_flow_active(session: dict, pizza_names: list[str]) -> bool:
    """Usa primero el estado estructurado del carrito y luego el historial."""
    if _get_cart_status(session) in _ACTIVE_CART_STATUSES:
        return True
    try:
        return is_order_flow_active(session["history"], pizza_names)
    except Exception:
        return False


def _response_confirms_order(content: str) -> bool:
    """Distingue una confirmación real del resumen que solo pregunta si confirma."""
    normalized = content.lower()
    return (
        "pedido confirmado" in normalized
        or "✅ pedido confirmado" in normalized
        or "orden confirmada" in normalized
    )


def _normalize_pizza_display_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        return "Pizza"
    if cleaned.lower().startswith("pizza "):
        return cleaned
    return f"Pizza {cleaned}"



class SecureChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=2000)
    use_cache: bool = True
    save_history: bool = True


class SecureQuickReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=500)


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
@measure_time
async def chat(
    req: SecureChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Chat con memoria por usuario + RAG contextual (robusto)."""
    if not state["ready"]:
        logger.info("Sistema de chat inicializando")
        return JSONResponse(content={
            "reply": "⏳ Sistema inicializando... Por favor espera unos segundos.",
            "is_order": False,
        })

    query = req.message.strip()
    if not query:
        logger.info("Mensaje de chat vacío rechazado")
        return JSONResponse(content={"reply": ""})

    # VULN-11/12/13: bloquear intentos de prompt injection y extracción de datos.
    if is_prompt_injection(query):
        logger.warning("Solicitud de chat bloqueada por política de seguridad")
        return JSONResponse(content={
            "reply": "No puedo procesar esa solicitud. Puedo ayudarte con el menú, precios o un pedido.",
            "is_order": False,
        })

    session = get_user_session(current_user.internal_id)
    logger.debug("Sesión de chat cargada; mensajes=%d", len(session["history"]))

    # ── Pizzas del RAG (robusto: nunca lanza) ───────────────────────
    try:
        pizza_names = rag_service.get_pizza_names()
    except Exception:
        pizza_names = []

    flow_active = _is_session_flow_active(session, pizza_names)

    # ── BUG 5: Bienvenida inteligente ───────────────────────────────
    # Si es el primer mensaje de la conversación (saludo o historial
    # vacío) y NO hay flujo activo, respondemos con bienvenida antes de
    # tocar RAG/LLM.
    is_greeting = (
        bool(_SALUDO_RE.search(query))
        and not is_new_order_query(query, pizza_names)
        and not has_order_intent(query)
        and not has_pizza_name(query, pizza_names)
    )

    # Mostrar bienvenida únicamente cuando el usuario realmente saluda.
    # El primer mensaje puede ser un pedido, una consulta informativa,
    # una solicitud de menú o cualquier otra intención válida y no debe
    # ser reemplazado automáticamente por la bienvenida.
    if is_greeting and not flow_active:
        welcome = await _build_welcome(req, session, pizza_names, current_user)
        if welcome is not None:
            if req.save_history:
                append_to_history(session, current_user.internal_id, query, welcome)
            return JSONResponse(content={
                "reply": welcome,
                "is_order": False,
            })

    # ── BUG 1: Repetir último pedido ────────────────────────────────
    last_order = get_last_order(session, current_user.internal_id)
    if _is_repeat_phrase(query) and last_order and last_order.is_valid():
        return await _handle_repeat_order(req, session, last_order, current_user)

    # ── BUG 3: Prioridad absoluta del flujo de pedido ────────────────
    # Si hay un flujo activo, NO consultamos RAG ni promociones. Usamos
    # únicamente el menú cacheado (con precios) para dar contexto al LLM
    # y seguimos exactamente donde quedó el flujo.
    if flow_active:
        return await _handle_active_flow(req, session, pizza_names, query, current_user)

    # ── Flujo normal (sin pedido activo) ────────────────────────────
    cache_key = None
    cache_allowed = req.use_cache and not _is_session_flow_active(session, pizza_names)
    if cache_allowed:
        cache_key = get_cache_key(query, current_user.internal_id)
        cached = response_cache.get(cache_key)
        if cached:
            logger.debug("Respuesta de chat servida desde caché")
            return JSONResponse(content=cached)

    try:
        is_new_order = is_new_order_query(query, pizza_names)

        history_text = "" if is_new_order else build_history_text(session)

        # RAG solo cuando NO hay flujo activo (prioridad del flujo).
        rag_context = await rag_service.retrieve_context(query)
        promos_text = rag_service.get_promos_text()
        
        # Si hay una pizza en el mensaje (nuevo pedido), agregar menú completo
        # para garantizar que TODOS los precios estén disponibles en el contexto
        menu_context = ""
        if has_pizza_name(query, pizza_names):
            menu_context = rag_service.get_menu_context()
            if menu_context:
                full_context = f"{menu_context}\n\n{rag_service.build_full_context(rag_context, promos_text)}"
            else:
                full_context = rag_service.build_full_context(rag_context, promos_text)
        else:
            full_context = rag_service.build_full_context(rag_context, promos_text)

        content = await llm_service.generate_response(
            context=full_context,
            history_text=history_text,
            question=query,
            history=session["history"],
            session=session,           # ← NUEVO: pasar sesión
            user_id=current_user.internal_id,       # ← NUEVO: pasar user_id
        )

        if req.save_history:
            append_to_history(session, current_user.internal_id, query, content)

        is_order, order_details = llm_service.extract_order_details(content)

        # ── Guardar último pedido confirmado (con observaciones) ─────
        if is_order and order_details:
            if _response_confirms_order(content):
                confirmed = LastOrder(
                    cantidad=int(order_details.get("cantidad", 1)) if order_details.get("cantidad") else 1,
                    producto=order_details.get("producto", ""),
                    tamaño=order_details.get("tamaño", "Grande"),
                    extras=order_details.get("extras", "Ninguno") or "Ninguno",
                    observaciones=order_details.get("observaciones", "") or "",
                    total=order_details.get("total", ""),
                )
                set_last_order(session, confirmed, current_user.internal_id)
                logger.info("Último pedido guardado en sesión cifrada")

        result = {
            "reply": content,
            "is_order": is_order,
            "order_details": order_details,
        }
        if cache_allowed and cache_key is not None:
            response_cache.set(cache_key, result)
        return JSONResponse(content=result)

    except Exception as e:
        logger.exception("Error procesando chat; activando respuesta degradada")
        # BUG 4: nunca devolvemos HTTP 500 por fallos internos. Respondemos
        # con un mensaje útil usando solo memoria conversacional.
        try:
            fallback = await llm_service.generate_response(
                context="",
                history_text=build_history_text(session),
                question=query,
                history=session["history"],
                session=session,           # ← NUEVO: pasar sesión
                user_id=current_user.internal_id,       # ← NUEVO: pasar user_id
            )
            if req.save_history:
                append_to_history(session, current_user.internal_id, query, fallback)
            return JSONResponse(content={
                "reply": fallback,
                "is_order": False,
            })
        except Exception:
            return JSONResponse(content={
                "reply": "Lo siento, tuve un problema procesando tu mensaje. ¿Podrías reformularlo?",
                "is_order": False,
            })


# ═══════════════════════════════════════════════════════════════════
# BUG 1: Repetir último pedido confirmado
# ═══════════════════════════════════════════════════════════════════

async def _handle_repeat_order(req: SecureChatRequest, session: dict, last_order: LastOrder, current_user: CurrentUser):
    """Reconstruye el último pedido y pregunta si confirmar de nuevo."""
    logger.info("Solicitud para repetir el último pedido")
    lines = [
        "Este fue tu último pedido:",
        "",
        f"📝 PEDIDO:",
        f"Cantidad: {last_order.cantidad}",
        f"Producto: {_normalize_pizza_display_name(last_order.producto)}",
        f"Tamaño: {last_order.tamaño}",
        f"Extras: {last_order.extras}",
    ]
    if last_order.observaciones:
        lines.append(f"Observaciones: {last_order.observaciones}")
    if last_order.total:
        lines.append(f"Total: {last_order.total}")
    lines.append("")
    lines.append("¿Deseas confirmarlo nuevamente? ✅")
    content = "\n".join(lines)

    if req.save_history:
        append_to_history(session, current_user.internal_id, req.message, content)
    return JSONResponse(content={
        "reply": content,
        "is_order": True,
        "order_details": last_order.to_dict(),
    })


# ═══════════════════════════════════════════════════════════════════
# BUG 3: Manejo del flujo activo (sin RAG, sin promos)
# ═══════════════════════════════════════════════════════════════════

async def _handle_active_flow(req: SecureChatRequest, session: dict, pizza_names: list, query: str, current_user: CurrentUser):
    """El flujo de pedido tiene prioridad absoluta: sin RAG ni promociones."""
    logger.debug("Flujo activo; RAG y promociones omitidos")
    # Inyectar SOLO el menú con precios para que el LLM tenga contexto de
    # precios/ingredientes sin salir del flujo.
    menu_context = rag_service.get_menu_context()
    context = menu_context or ""
    history_text = build_history_text(session)

    try:
        content = await llm_service.generate_response(
            context=context,
            history_text=history_text,
            question=query,
            history=session["history"],
            session=session,           # ← NUEVO: pasar sesión
            user_id=current_user.internal_id,       # ← NUEVO: pasar user_id
        )
        if req.save_history:
            append_to_history(session, current_user.internal_id, query, content)
        is_order, order_details = llm_service.extract_order_details(content)

        # Guardar último pedido confirmado si aplica
        if is_order and order_details:
            if _response_confirms_order(content):
                confirmed = LastOrder(
                    cantidad=int(order_details.get("cantidad", 1)) if order_details.get("cantidad") else 1,
                    producto=order_details.get("producto", ""),
                    tamaño=order_details.get("tamaño", "Grande"),
                    extras=order_details.get("extras", "Ninguno") or "Ninguno",
                    observaciones=order_details.get("observaciones", "") or "",
                    total=order_details.get("total", ""),
                )
                set_last_order(session, confirmed, current_user.internal_id)

        return JSONResponse(content={
            "reply": content,
            "is_order": is_order,
            "order_details": order_details,
        })
    except Exception as e:
        logger.exception("Error en flujo activo; activando respuesta degradada")
        return JSONResponse(content={
            "reply": "¿En qué puedo continuar con tu pedido?",
            "is_order": True,
        })


# ═══════════════════════════════════════════════════════════════════
# BUG 5: Bienvenida inteligente
# ═══════════════════════════════════════════════════════════════════

async def _build_welcome(req: SecureChatRequest, session: dict, pizza_names: list, current_user: CurrentUser) -> Optional[str]:
    """Construye la bienvenida según si el usuario tiene pedidos previos.

    Devuelve None si no aplica (para que el flujo normal continúe).
    Caso A (tiene pedido previo): muestra último pedido + ofrece repetir.
    Caso B (nuevo): muestra producto más vendido + menú completo.
    """
    last_order = get_last_order(session, current_user.internal_id)

    # Esperar a que el menú esté cargado antes de mostrarlo (BUG 2):
    # si el menú aún no está listo, damos una bienvenida breve sin precios
    # en vez de mostrar '[precio no disponible]'.
    menu = rag_service.get_menu_context()

    if last_order and last_order.is_valid():
        # ── CASO A ──
        lines = [
            f"¡Hola! 🍕",
            "",
            "La última vez pediste:",
            "",
            f"• {_normalize_pizza_display_name(last_order.producto)} {last_order.tamaño}",
        ]
        extras = last_order.extras if last_order.extras not in ("Ninguno", "", None) else "Sin extras"
        lines.append(f"• Extras: {extras}")
        if last_order.total:
            lines.append(f"• Total: {last_order.total}")
        lines.append("")
        lines.append("¿Te gustaría pedir lo mismo o prefieres ver el menú?")
        return "\n".join(lines)

    # ── CASO B (nuevo cliente) ──
    best = rag_service.get_best_seller()
    lines = [
        "¡Hola! 🍕 Bienvenido a Pizzería 220.",
        "",
        "⭐ Nuestra pizza más vendida es:",
        "",
        f"{_normalize_pizza_display_name(best['nombre'])}",
    ]
    if best["precio"] and best["precio"] != "consultar":
        lines.append(f"{best['precio']} MXN")
    if best["ingredientes"] and best["ingredientes"] != "consultar en el menú":
        lines.append("")
        lines.append(f"Ingredientes: {best['ingredientes']}")
    lines.append("")
    if menu:
        formatted_menu = rag_service.format_menu_for_display().strip()
        lines.append(formatted_menu)

        normalized_menu = formatted_menu.lower()
        already_has_question = (
            "cuál te gustaría ordenar" in normalized_menu
            or "cual te gustaria ordenar" in normalized_menu
        )
        if not already_has_question:
            lines.append("")
            lines.append("¿Cuál te gustaría ordenar?")
    else:
        lines.append("🍕 Nuestro menú se está cargando, en un momento lo vemos completo.")
        lines.append("")
        lines.append("¿Cuál te gustaría ordenar?")

    return "\n".join(lines)


@router.post("/quick")
async def quick_reply(
    req: SecureQuickReplyRequest,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Respuestas rápidas predefinidas; cae en /chat si no hay match."""
    if is_prompt_injection(req.message):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solicitud no permitida",
        )
    query = req.message.lower().strip()

    menu_keywords = [
        "menu", "menú", "que pizzas tienen", "qué pizzas tienen",
        "pizzas", "carta", "que venden", "qué venden", "productos",
    ]
    if any(kw in query for kw in menu_keywords):
        # Reutiliza el mismo menú que la bienvenida (BUG 5 / BUG 2).
        menu = rag_service.get_menu_context()
        if menu:
            return {
                "reply": "🍕 Claro, aquí tienes nuestro menú:\n\n" + rag_service.format_menu_for_display(),
                "is_order": False,
                "quick": True,
            }
        return {
            "reply": "🍕 Claro, aquí tienes nuestro menú. ¿Qué pizza te gustaría ordenar?",
            "is_order": False,
            "quick": True,
        }

    quick_map = {
        "horario":   "🕒 Nuestro horario es de Lunes a Domingo de 6 PM a 12 AM.",
        "telefono":  "📞 Puedes contactarnos al: 555-123-4567",
        "direccion": "📍 Estamos en: Calle Principal #220, Centro",
        "ubicación": "📍 Estamos en: Calle Principal #220, Centro",
        "pago":      "💳 Aceptamos: Efectivo, Tarjeta y Transferencia",
    }
    for key, response in quick_map.items():
        if key in query:
            return {"reply": response, "is_order": False, "quick": True}

    return await chat(
        SecureChatRequest(message=req.message),
        current_user,
    )


@router.get("/extras")
async def available_extras(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Entrega al frontend el catálogo calculado por la misma fuente RAG."""
    del current_user
    context = rag_service.get_available_extras_context()
    extras: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in context.splitlines():
        match = re.search(
            r"^[•*\-\s]*(.+?)\s*(?:—|-)\s*\$\s*([0-9]+(?:[.,][0-9]{1,2})?)",
            line.strip(),
        )
        if not match:
            continue
        name = match.group(1).strip(" •*-")
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        price = float(match.group(2).replace(",", "."))
        extras.append({"name": name, "price": f"${price:.2f} MXN"})
    return {"extras": extras[:50]}


@router.get("/history")
async def history(
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
):
    limit = max(1, min(limit, 100))
    messages = get_chat_history(current_user.internal_id, limit=limit)
    return JSONResponse({
        "messages_count": len(messages),
        "history": messages,
    })


@router.delete("/history")
async def delete_history(
    current_user: CurrentUser = Depends(get_current_user),
):
    success = delete_chat_history(current_user.internal_id)
    clear_last_order(
        get_user_session(current_user.internal_id),
        current_user.internal_id,
    )
    return JSONResponse({
        "status": "ok" if success else "error",
        "deleted": success,
    })
