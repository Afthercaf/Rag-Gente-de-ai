from typing import Any, Dict
from services.history_service import load_history, append_message, clear_history

# Memoria de conversación por usuario (en sesión)
USER_SESSIONS: Dict[int, Dict[str, Any]] = {}


def get_user_session(user_id: int) -> Dict[str, Any]:
    """Retorna (o crea) la sesión de conversación de un usuario, cargando historial persistido."""
    if user_id not in USER_SESSIONS:
        # Cargar historial persistido desde disco
        persistent_history = load_history(user_id)
        USER_SESSIONS[user_id] = {"history": persistent_history}
    return USER_SESSIONS[user_id]


def append_to_history(session: Dict[str, Any], user_id: int, user_msg: str, assistant_msg: str) -> None:
    """Agrega un intercambio al historial y lo persiste a disco."""
    session["history"].append({"user": user_msg, "assistant": assistant_msg})
    session["history"] = session["history"][-20:]
    
    # Guardar en disco
    append_message(user_id, user_msg, assistant_msg, limit=20)


def build_history_text(session: Dict[str, Any], last_n: int = 10) -> str:
    """Formatea los últimos N intercambios para el prompt."""
    return "\n".join(
        f"Cliente: {msg['user']}\nAsistente: {msg['assistant']}"
        for msg in session["history"][-last_n:]
    )


def build_enriched_query(session: Dict[str, Any], query: str, last_n: int = 3) -> str:
    """Enriquece la query con contexto reciente para mejorar la búsqueda RAG."""
    if not session["history"]:
        return query
    recent = " ".join(item["user"] for item in session["history"][-last_n:])
    return f"{recent} {query}"
