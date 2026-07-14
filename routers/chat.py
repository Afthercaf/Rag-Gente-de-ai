import re
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agents.router import RouterAgent  # 🆕 NUEVA IMPORTACIÓN
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

# 🆕 Instancia del router multi-agente (creada una sola vez)
router_agent = RouterAgent()

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
    """Chat con arquitectura multi-agente."""
    print("\n" + "=" * 60)
    print(f"🚀 [CHAT] Nueva solicitud recibida")
    print(f"📝 [CHAT] user_id: {req.user_id}")
    print(f"📝 [CHAT] message: '{req.message}'")
    print(f"📝 [CHAT] use_cache: {req.use_cache}")
    print("=" * 60)

    if not state["ready"]:
        print("⏳ [CHAT] Sistema NO listo - inicializando...")
        return JSONResponse(content={
            "reply": "⏳ Sistema inicializando... Por favor espera unos segundos.",
            "is_order": False,
        })

    query = req.message.strip()
    if not query:
        print("⚠️ [CHAT] Mensaje vacío")
        return JSONResponse(content={"reply": ""})

    session = get_user_session(req.user_id)
    print(f"👤 [CHAT] Usuario: {req.user_id} | 🧠 Historial: {len(session['history'])} msgs")

    # ── Pizzas del RAG + ¿hay un flujo de pedido activo? ──────────
    try:
        pizza_names = rag_service.get_pizza_names()
        print(f"🍕 [CHAT] Pizzas del RAG: {pizza_names}")
    except Exception as e:
        print(f"⚠️ [CHAT] Error obteniendo pizza_names: {e}")
        pizza_names = []
    
    flow_active = is_order_flow_active(session["history"], pizza_names)

    # Cache - solo si no hay flujo activo
    cache_key = None
    if req.use_cache and not flow_active:
        cache_key = get_cache_key(f"{req.user_id}:{query}")
        cached = response_cache.get(cache_key)
        if cached:
            print(f"📦 [CHAT] Respuesta desde caché")
            print(f"📦 [CHAT] Contenido: {cached.get('reply', '')[:100]}...")
            return JSONResponse(content=cached)

    try:
        # 🆕 USAR EL ROUTER MULTI-AGENTE
        print("\n🤖 [CHAT] Delegando al RouterAgent...")
        result = await router_agent.route(
            query=query,
            history=session["history"],
            user_id=req.user_id,
            use_cache=req.use_cache,
        )
        
        print(f"📥 [CHAT] Respuesta del agente recibida")
        print(f"📥 [CHAT] Agente: {result.get('agent', 'unknown')}")
        print(f"📥 [CHAT] Longitud respuesta: {len(result.get('reply', ''))}")
        print(f"📥 [CHAT] ¿Es orden? {result.get('is_order', False)}")

        # Guardar historial
        if req.save_history:
            append_to_history(session, req.user_id, query, result["reply"])
            print(f"💾 [CHAT] Historial guardado")

        # Guardar en caché si corresponde
        if req.use_cache and cache_key is not None and not flow_active:
            response_cache.set(cache_key, result)
            print(f"💾 [CHAT] Guardado en caché")

        print(f"📤 [CHAT] Respuesta final - Agente: {result.get('agent', 'unknown')}")
        print("=" * 60 + "\n")

        return JSONResponse(content=result)

    except Exception as e:
        import traceback
        print(f"❌ [CHAT] Error en /chat: {e}")
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