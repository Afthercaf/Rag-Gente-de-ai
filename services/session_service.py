from typing import Any, Dict, List

from src.supabase_chat import delete_chat_history, get_chat_history, insert_chat_history

# Memoria de conversación por usuario
USER_SESSIONS: Dict[int, Dict[str, Any]] = {}


def _normalize_history_records(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Convierte registros de Supabase en pares {user, assistant}.
    
    CORRECCIÓN: Ahora maneja correctamente los casos donde un mensaje
    puede venir sin su par correspondiente.
    """
    history: List[Dict[str, str]] = []
    current: Dict[str, str] = {"user": "", "assistant": ""}

    for msg in records:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            # Si ya hay un par anterior incompleto, guardarlo primero
            if current.get("user") and not current.get("assistant"):
                # Intentar buscar el assistant en el siguiente mensaje
                # pero por ahora guardamos lo que tenemos
                history.append(current)
                current = {"user": "", "assistant": ""}
            current["user"] = content
        elif role == "assistant":
            if not current.get("user"):
                # Si no hay user, crear un par vacío
                current = {"user": "", "assistant": content}
                history.append(current)
                current = {"user": "", "assistant": ""}
            else:
                current["assistant"] = content
                history.append(current)
                current = {"user": "", "assistant": ""}

    # Si quedó algo pendiente, guardarlo
    if current.get("user") or current.get("assistant"):
        if not current.get("assistant"):
            current["assistant"] = ""
        history.append(current)

    return history


def get_user_session(user_id: int) -> Dict[str, Any]:
    """Retorna (o crea) la sesión de conversación de un usuario."""
    if user_id not in USER_SESSIONS:
        if user_id > 0:
            raw_history = get_chat_history(user_id, limit=20)
            history = _normalize_history_records(raw_history)
        else:
            history = []
        USER_SESSIONS[user_id] = {"history": history}
    return USER_SESSIONS[user_id]


def append_to_history(session: Dict[str, Any], user_id: int, user_msg: str, assistant_msg: str) -> None:
    """Agrega un intercambio al historial, lo limita a los últimos 20 mensajes y lo persiste."""
    exchange = {"user": user_msg, "assistant": assistant_msg}
    session["history"].append(exchange)
    session["history"] = session["history"][-20:]

    if user_id > 0:
        # CORRECCIÓN: antes solo se insertaba el mensaje "user" y el "assistant"
        # nunca se persistía en Supabase. Esto provocaba que, al reconstruir el
        # historial tras un reinicio del proceso (ej. uvicorn --reload), todos
        # los registros tuvieran role="user" y _normalize_history_records
        # generara pares con "assistant": "" — rompiendo _get_flow_start, que
        # depende de encontrar "tamaño" en el texto del asistente para detectar
        # el inicio del flujo de pedido. Sin esa señal, el flujo activo se
        # perdía por completo y build_directive caía siempre al caso default
        # ("No hay datos disponibles.").
        insert_chat_history(user_id, "user", user_msg)
        insert_chat_history(user_id, "assistant", assistant_msg)


def build_history_text(session: Dict[str, Any], last_n: int = 10) -> str:
    """Formatea los últimos N intercambios para el prompt."""
    lines = []
    for msg in session["history"][-last_n:]:
        user_text = msg.get("user", "")
        assistant_text = msg.get("assistant", "")
        if user_text:
            lines.append(f"Cliente: {user_text}")
        if assistant_text:
            lines.append(f"Asistente: {assistant_text}")
    return "\n".join(lines)


def build_enriched_query(session: Dict[str, Any], query: str, last_n: int = 3) -> str:
    """Enriquece la query con contexto reciente para mejorar la búsqueda RAG."""
    if not session["history"]:
        return query
    recent = " ".join(item["user"] for item in session["history"][-last_n:])
    return f"{recent} {query}"