"""
Servicio de sesiones con Redis persistente + encriptación AES-256-GCM.

Reemplaza el antiguo diccionario en memoria (USER_SESSIONS) por Redis,
manteniendo la misma API pública para compatibilidad con chat.py y llm_service.py.

Cada sesión se almacena en Redis encriptada con AES-256-GCM.
Se mantiene un cache local en memoria (LRU simple) para evitar lecturas
innecesarias a Redis en cada operación.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

from core.session_store import session_store
from src.supabase_chat import delete_chat_history, get_chat_history, insert_chat_history

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
# Cache local en memoria (write-through: cada modificación persiste en Redis)
# ──────────────────────────────────────────────────────────────────────

class _SessionCache:
    """Cache local LRU simple con write-through a Redis.

    Cada vez que se modifica una sesión, se escribe inmediatamente a Redis
    de forma asíncrona. La lectura prefiere el cache local; si no está,
    se lee de Redis.
    """

    def __init__(self, max_size: int = 500):
        self._cache: Dict[int, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._max_size = max_size

    def get(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._cache.get(user_id)

    def set(self, user_id: int, data: Dict[str, Any]) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evitar crecimiento infinito: eliminar el primero
                oldest = next(iter(self._cache))
                del self._cache[oldest]
            self._cache[user_id] = data

    def remove(self, user_id: int) -> None:
        with self._lock:
            self._cache.pop(user_id, None)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._cache)


_local_cache = _SessionCache()


# ──────────────────────────────────────────────────────────────────────
# ALMACENAMIENTO DE ÚLTIMO PEDIDO CONFIRMADO
# ──────────────────────────────────────────────────────────────────────

class LastOrder:
    """Almacena los detalles completos del último pedido confirmado."""
    def __init__(
        self,
        cantidad: int = 1,
        producto: str = "",
        tamaño: str = "Grande",
        extras: str = "Ninguno",
        observaciones: str = "",
        total: str = "",
    ):
        self.cantidad = cantidad
        self.producto = producto
        self.tamaño = tamaño
        self.extras = extras
        self.observaciones = observaciones
        self.total = total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cantidad": self.cantidad,
            "producto": self.producto,
            "tamaño": self.tamaño,
            "extras": self.extras,
            "observaciones": self.observaciones,
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LastOrder":
        return cls(
            cantidad=data.get("cantidad", 1),
            producto=data.get("producto", ""),
            tamaño=data.get("tamaño", "Grande"),
            extras=data.get("extras", "Ninguno"),
            observaciones=data.get("observaciones", ""),
            total=data.get("total", ""),
        )

    def is_valid(self) -> bool:
        return bool(self.producto and self.producto.strip())


def get_last_order(session: Dict[str, Any], user_id: int = 0) -> Optional[LastOrder]:
    """Obtiene el último pedido de la sesión cifrada en Redis."""
    last_order_data = session.get("last_order")
    order = LastOrder.from_dict(last_order_data) if last_order_data else None
    return order if order and order.is_valid() else None


def set_last_order(session: Dict[str, Any], order: LastOrder, user_id: int = 0) -> None:
    """Guarda el último pedido en la sesión cifrada en Redis."""
    session["last_order"] = order.to_dict()
    if user_id:
        _schedule_redis_persist(user_id, session)


def clear_last_order(session: Dict[str, Any], user_id: int = 0) -> None:
    """Limpia el último pedido de la sesión cifrada."""
    session.pop("last_order", None)
    if user_id:
        _schedule_redis_persist(user_id, session)


# ──────────────────────────────────────────────────────────────────────
# FUNCIONES DE HISTORIAL
# ──────────────────────────────────────────────────────────────────────

def _normalize_history_records(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Convierte registros de Supabase en pares {user, assistant}."""
    history: List[Dict[str, str]] = []
    current: Dict[str, str] = {"user": "", "assistant": ""}

    for msg in records:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            if current.get("user") and not current.get("assistant"):
                history.append(current)
                current = {"user": "", "assistant": ""}
            current["user"] = content
        elif role == "assistant":
            if not current.get("user"):
                current = {"user": "", "assistant": content}
                history.append(current)
                current = {"user": "", "assistant": ""}
            else:
                current["assistant"] = content
                history.append(current)
                current = {"user": "", "assistant": ""}

    if current.get("user") or current.get("assistant"):
        if not current.get("assistant"):
            current["assistant"] = ""
        history.append(current)

    return history


async def _persist_session_to_redis(user_id: int, data: Dict[str, Any]) -> None:
    """Guarda la sesión en Redis (encriptada) sin bloquear."""
    try:
        await session_store.set(user_id, data)
    except Exception as exc:
        logger.warning("No se pudo persistir sesión en Redis: %s", exc)


def get_user_session(user_id: int) -> Dict[str, Any]:
    """Retorna una sesión completamente aislada para cada usuario.

    Lee primero del cache local; si no está, intenta Redis; si tampoco,
    crea una nueva sesión desde Supabase.

    Cada user_id obtiene:
    - historial independiente
    - carrito independiente
    - último pedido independiente
    - propietario explícito de la sesión
    """
    normalized_id = _normalized_user_id(user_id)
    if normalized_id is None:
        raise ValueError("user_id inválido")

    # 1. Intentar cache local
    session = _local_cache.get(normalized_id)
    if session is not None:
        return session

    # 2. Intentar Redis (sesión persistente)
    redis_session = session_store.get_sync(normalized_id)

    if redis_session is not None:
        # Reparar sesiones legacy
        redis_session["user_id"] = normalized_id
        redis_session.setdefault("history", [])
        redis_session.setdefault("current_cart", None)
        redis_session.setdefault("last_order", None)
        _local_cache.set(normalized_id, redis_session)
        return redis_session

    # 3. Crear nueva sesión desde Supabase
    history = get_chat_history(normalized_id, limit=50)
    session = {
        "user_id": normalized_id,
        "history": history,
        "current_cart": None,
        "last_order": None,
    }
    _local_cache.set(normalized_id, session)

    # Persistir en Redis en background (fire-and-forget)
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                _persist_session_to_redis(normalized_id, session), loop
            )
    except Exception:
        pass

    return session


def append_to_history(session: Dict[str, Any], user_id: int, user_msg: str, assistant_msg: str) -> None:
    """Agrega un intercambio sin permitir contaminación entre usuarios."""
    owner_id = session.get("user_id")
    if owner_id is not None and owner_id != user_id:
        raise ValueError(f"La sesión pertenece al usuario {owner_id}, no al usuario {user_id}")
    exchange = {"user": user_msg, "assistant": assistant_msg}
    session["history"].append(exchange)
    session["history"] = session["history"][-20:]

    if user_id > 0:
        insert_chat_history(user_id, "user", user_msg)
        insert_chat_history(user_id, "assistant", assistant_msg)

    # Persistir en Redis
    _schedule_redis_persist(user_id, session)


def build_history_text(session: Dict[str, Any], last_n: int = 10) -> str:
    """Formatea historial delimitado, omitiendo instrucciones sospechosas."""
    from services.intent_detector import is_prompt_injection

    lines = []
    for msg in session["history"][-last_n:]:
        user_text = str(msg.get("user", ""))[:2000]
        assistant_text = str(msg.get("assistant", ""))[:4000]
        if user_text:
            safe_user_text = (
                "[mensaje omitido por política de seguridad]"
                if is_prompt_injection(user_text)
                else user_text
            )
            lines.append(f"Cliente (dato no confiable): {safe_user_text}")
        if assistant_text:
            lines.append(f"Asistente: {assistant_text}")
    return "\n".join(lines)


def build_enriched_query(session: Dict[str, Any], query: str, last_n: int = 3) -> str:
    """Enriquece la query con contexto reciente para mejorar la búsqueda RAG."""
    if not session["history"]:
        return query
    recent = " ".join(item["user"] for item in session["history"][-last_n:])
    return f"{recent} {query}"


# ──────────────────────────────────────────────────────────────────────
# CARRITO ACTIVO AISLADO POR USUARIO
# ──────────────────────────────────────────────────────────────────────

def _normalized_user_id(value: Any) -> Optional[int]:
    """Normaliza IDs provenientes de JSON, formularios o memoria."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _schedule_redis_persist(user_id: int, session: Dict[str, Any]) -> None:
    """Write-through inmediato para no perder transiciones del carrito."""
    if user_id:
        session_store.set_sync(user_id, session)


def get_current_cart(session: Dict[str, Any], user_id: int = 0) -> Optional[Dict[str, Any]]:
    """Retorna el carrito de la sesión y repara propietarios legacy."""
    requested_id = _normalized_user_id(user_id)
    session_owner = _normalized_user_id(session.get("user_id"))

    if requested_id and session_owner and session_owner != requested_id:
        raise ValueError("Intento de leer un carrito perteneciente a otro usuario")

    cart = session.get("current_cart")
    if not cart:
        return None

    cart_owner = _normalized_user_id(cart.get("user_id"))

    # Reparar carritos legacy sin propietario válido.
    if requested_id and cart_owner in (None, 0):
        cart["user_id"] = requested_id
        cart_owner = requested_id

    if requested_id and cart_owner and cart_owner != requested_id:
        raise ValueError("El carrito activo pertenece a otro usuario")

    return cart


def set_current_cart(session: Dict[str, Any], user_id: int, cart: Dict[str, Any]) -> Dict[str, Any]:
    """Asigna el mismo carrito mutable a la sesión del usuario."""
    requested_id = _normalized_user_id(user_id) or 0
    owner_id = _normalized_user_id(session.get("user_id"))

    if owner_id and requested_id and owner_id != requested_id:
        raise ValueError("No se puede asignar un carrito a la sesión de otro usuario")

    cart["user_id"] = requested_id
    session["current_cart"] = cart

    # Persistir en Redis
    _schedule_redis_persist(requested_id or user_id, session)
    return cart


def clear_current_cart(session: Dict[str, Any], user_id: int = 0) -> None:
    """Elimina solo el carrito de la sesión indicada."""
    owner_id = session.get("user_id")
    if user_id and owner_id is not None and owner_id != user_id:
        raise ValueError("No se puede limpiar el carrito de otro usuario")
    session["current_cart"] = None

    # Persistir en Redis
    if user_id:
        _schedule_redis_persist(user_id, session)


def new_cart(user_id: int, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Crea el estado serializable de un pedido multi-ítem."""
    return {
        "user_id": user_id,
        "status": "collecting_extras",
        "cursor": 0,
        "items": items,
        "observations": [],
    }


def clear_user_session(user_id: int) -> None:
    """Elimina la sesión del usuario del cache local y de Redis."""
    normalized_id = _normalized_user_id(user_id)
    if normalized_id is None:
        return
    _local_cache.remove(normalized_id)
    # Eliminar de Redis en background
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                session_store.delete(normalized_id), loop
            )
    except Exception:
        pass


def clear_all_sessions() -> None:
    """Elimina todas las sesiones del cache local y de Redis."""
    _local_cache.clear()
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.run_coroutine_threadsafe(
                session_store.clear_all(), loop
            )
    except Exception:
        pass


def get_active_session_count() -> int:
    """Cantidad de usuarios con sesión activa en cache local."""
    return _local_cache.size()
