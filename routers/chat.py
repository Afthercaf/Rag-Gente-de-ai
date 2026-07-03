import re

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from core.cache import response_cache
from core.decorators import measure_time
from core.state import state
from schemas.chat import ChatRequest, QuickReplyRequest
from services import llm_service, rag_service
from services.intent_detector import is_order_flow_active
from services.session_service import (
    append_to_history,
    build_enriched_query,
    build_history_text,
    get_user_session,
)
from src.supabase_chat import delete_chat_history, get_chat_history
from utils.cache_keys import get_cache_key


# ✅ Ahora recibe pizza_names dinámico desde RAG
def is_new_order_query(query: str, pizza_names: list[str]) -> bool:
    text = query.lower()

    has_order_intent = bool(
        re.search(r"\b(quiero|dame|ordenar|pedir|trae|me das)\b", text)
    )

    has_pizza_reference = "pizza" in text or any(
        name in text for name in pizza_names
    )

    return has_order_intent and has_pizza_reference


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
@measure_time
async def chat(req: ChatRequest):
    """Chat con memoria por usuario + RAG contextual."""
    if not state["ready"]:
        return JSONResponse(content={
            "reply": "⏳ Sistema inicializando... Por favor espera unos segundos.",
            "is_order": False,
        })

    query = req.message.strip()
    if not query:
        return JSONResponse(content={"reply": ""})

    session = get_user_session(req.user_id)
    print(f"👤 Usuario: {req.user_id} | 🧠 Historial: {len(session['history'])} msgs")

    # ── Pizzas del RAG + ¿hay un flujo de pedido activo? ──────────
    # Se necesita saber esto ANTES de consultar la caché (ver más
    # abajo). Si falla la consulta al RAG aquí, no se rompe el
    # endpoint completo — se asume "sin flujo activo" y se continúa;
    # cualquier error real durante la generación de la respuesta lo
    # sigue cubriendo el try/except de abajo.
    try:
        pizza_names = rag_service.get_pizza_names()
    except Exception:
        pizza_names = []
    flow_active = is_order_flow_active(session["history"], pizza_names)

    # Cache
    # FIX: la caché se indexaba SOLO por "user_id:texto del mensaje",
    # sin considerar en qué paso del flujo de pedido está el cliente.
    # Eso hacía que un "no" (o cualquier texto repetido más tarde en la
    # misma conversación) devolviera, desde caché, la respuesta de OTRO
    # punto del flujo en vez de avanzar el paso actual de ingredientes/
    # extras — exactamente el riesgo que ya advertía la documentación
    # de is_order_flow_active() en intent_detector.py, pero que nunca
    # se conectó aquí. Mientras el flujo está activo, la respuesta
    # correcta depende del HISTORIAL completo, no solo del texto del
    # mensaje — así que se omite la caché por completo en ese caso.
    cache_key = None
    if req.use_cache and not flow_active:
        cache_key = get_cache_key(f"{req.user_id}:{query}")
        cached = response_cache.get(cache_key)
        if cached:
            print("📦 Respuesta desde caché")
            return JSONResponse(content=cached)

    try:
        # ✅ Nombres dinámicos desde RAG (ya obtenidos arriba)
        is_new_order = is_new_order_query(query, pizza_names)
        print(f"🍕 Pizzas detectadas del RAG: {pizza_names}")
        print(f"🆕 Es nuevo pedido: {is_new_order}")

        history_text = "" if is_new_order else build_history_text(session)
        search_query = query
        print(f"🔍 Búsqueda RAG: {search_query}")

        rag_context = await rag_service.retrieve_context(search_query)
        promos_text = rag_service.get_promos_text()
        full_context = rag_service.build_full_context(rag_context, promos_text)

        content = await llm_service.generate_response(
            context=full_context,
            history_text=history_text,
            question=query,
            history=session["history"],
        )

        if req.save_history:
            append_to_history(session, req.user_id, query, content)

        is_order, order_details = llm_service.extract_order_details(content)

        result = {
            "reply": content,
            "is_order": is_order,
            "order_details": order_details,
            "user_id": req.user_id,
        }

        if req.use_cache and cache_key is not None:
            response_cache.set(cache_key, result)

        return JSONResponse(content=result)

    except Exception as e:
        import traceback
        print(f"❌ Error en /chat: {e}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={
                "reply": "❌ Error interno del servidor. Por favor intenta nuevamente.",
                "is_order": False,
            },
        )


@router.post("/quick")
async def quick_reply(req: QuickReplyRequest):
    """Respuestas rápidas predefinidas; cae en /chat si no hay match."""
    query = req.message.lower().strip()

    menu_keywords = [
        "menu", "menú", "que pizzas tienen", "qué pizzas tienen",
        "pizzas", "carta", "que venden", "qué venden", "productos",
    ]
    if any(kw in query for kw in menu_keywords):
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

    # Fallback al chat completo (user_id genérico para quick replies)
    return await chat(ChatRequest(user_id=0, message=req.message))


@router.get("/history/{user_id}")
async def history(user_id: int, limit: int = 50):
    """Obtiene el historial de conversación del usuario desde Supabase."""
    messages = get_chat_history(user_id, limit=limit)
    return JSONResponse({
        "user_id": user_id,
        "messages_count": len(messages),
        "history": messages,
    })


@router.delete("/history/{user_id}")
async def delete_history(user_id: int):
    """Elimina el historial de conversación del usuario en Supabase."""
    success = delete_chat_history(user_id)
    return JSONResponse({
        "status": "ok" if success else "error",
        "user_id": user_id,
        "deleted": success,
    })