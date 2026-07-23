import os
import sqlite3
from typing import Any, Dict, List, Optional

from src.supabase_chat import delete_chat_history, get_chat_history, insert_chat_history


# ──────────────────────────────────────────────────────────────────────
# PERSISTENCIA DEL ÚLTIMO PEDIDO
# El último pedido confirmado se guarda en SQLite local para que sobreviva
# a reinicios del proceso (la memoria en USER_SESSIONS se pierde).
# ──────────────────────────────────────────────────────────────────────

_LAST_ORDER_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "last_orders.db")


def _get_last_order_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_LAST_ORDER_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS last_orders (
            user_id INTEGER PRIMARY KEY,
            cantidad INTEGER,
            producto TEXT,
            tamano TEXT,
            extras TEXT,
            observaciones TEXT,
            total TEXT
        )
        """
    )
    return conn


def _persist_last_order(user_id: int, order: "LastOrder") -> None:
    try:
        conn = _get_last_order_conn()
        conn.execute(
            """
            INSERT INTO last_orders
                (user_id, cantidad, producto, tamano, extras, observaciones, total)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                cantidad=excluded.cantidad,
                producto=excluded.producto,
                tamano=excluded.tamano,
                extras=excluded.extras,
                observaciones=excluded.observaciones,
                total=excluded.total
            """,
            (
                user_id, order.cantidad, order.producto, order.tamaño,
                order.extras, order.observaciones, order.total,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning("No se pudo persistir el último pedido: %s", exc)


def _load_persisted_last_order(user_id: int) -> Optional["LastOrder"]:
    try:
        conn = _get_last_order_conn()
        row = conn.execute(
            "SELECT cantidad, producto, tamano, extras, observaciones, total "
            "FROM last_orders WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        conn.close()
        if not row:
            return None
        return LastOrder(
            cantidad=row[0],
            producto=row[1],
            tamaño=row[2],
            extras=row[3],
            observaciones=row[4] or "",
            total=row[5],
        )
    except Exception:
        return None


# Memoria de conversación por usuario
USER_SESSIONS: Dict[int, Dict[str, Any]] = {}

# Alias interno usado por las funciones multiusuario. Ambos nombres apuntan
# al mismo diccionario para conservar compatibilidad con el código existente.
_sessions = USER_SESSIONS


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
    """Obtiene el último pedido confirmado (memoria + persistencia)."""
    last_order_data = session.get("last_order")
    in_memory = LastOrder.from_dict(last_order_data) if last_order_data else None
    persisted = _load_persisted_last_order(user_id) if user_id else None
    if in_memory and in_memory.is_valid():
        return in_memory
    if persisted and persisted.is_valid():
        session["last_order"] = persisted.to_dict()
        return persisted
    return in_memory or persisted


def set_last_order(session: Dict[str, Any], order: LastOrder, user_id: int = 0) -> None:
    """Guarda el último pedido confirmado en la sesión (y lo persiste)."""
    session["last_order"] = order.to_dict()
    if user_id:
        _persist_last_order(user_id, order)


def clear_last_order(session: Dict[str, Any], user_id: int = 0) -> None:
    """Limpia el último pedido confirmado (memoria + persistencia)."""
    session.pop("last_order", None)
    if user_id:
        try:
            conn = _get_last_order_conn()
            conn.execute("DELETE FROM last_orders WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
        except Exception:
            pass


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


def get_user_session(user_id: int) -> Dict[str, Any]:
    """Retorna una sesión completamente aislada para cada usuario.

    Cada user_id obtiene:
    - historial independiente
    - carrito independiente
    - último pedido independiente
    - propietario explícito de la sesión
    """
    normalized_id = _normalized_user_id(user_id)
    if normalized_id is None:
        raise ValueError("user_id inválido")

    session = _sessions.get(normalized_id)

    if session is None:
        history = get_chat_history(normalized_id, limit=50)
        session = {
            "user_id": normalized_id,
            "history": history,
            "current_cart": None,
            "last_order": None,
        }
        _sessions[normalized_id] = session
        return session

    # Reparación de sesiones antiguas creadas antes del soporte multiusuario.
    session["user_id"] = normalized_id
    session.setdefault("history", [])
    session.setdefault("current_cart", None)
    session.setdefault("last_order", None)

    cart = session.get("current_cart")
    if isinstance(cart, dict):
        cart_owner = _normalized_user_id(cart.get("user_id"))
        if cart_owner in (None, 0):
            cart["user_id"] = normalized_id
        elif cart_owner != normalized_id:
            # Nunca reutilizar un carrito de otro usuario dentro de esta sesión.
            session["current_cart"] = None

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


def get_current_cart(session: Dict[str, Any], user_id: int = 0) -> Optional[Dict[str, Any]]:
    """Retorna el carrito de la sesión y repara propietarios legacy.

    Los carritos antiguos podían quedar con user_id=0, None o como cadena.
    Si el carrito vive dentro de la sesión correcta, se reasigna al usuario
    actual. Un ID positivo realmente diferente sigue siendo rechazado.
    """
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
    """Asigna el mismo carrito mutable a la sesión del usuario.

    No crea una copia: build_directive modifica este diccionario durante el
    flujo y esos cambios deben permanecer disponibles en la siguiente petición.
    """
    requested_id = _normalized_user_id(user_id) or 0
    owner_id = _normalized_user_id(session.get("user_id"))

    if owner_id and requested_id and owner_id != requested_id:
        raise ValueError("No se puede asignar un carrito a la sesión de otro usuario")

    cart["user_id"] = requested_id
    session["current_cart"] = cart
    return cart

def clear_current_cart(session: Dict[str, Any], user_id: int = 0) -> None:
    """Elimina solo el carrito de la sesión indicada."""
    owner_id = session.get("user_id")
    if user_id and owner_id is not None and owner_id != user_id:
        raise ValueError("No se puede limpiar el carrito de otro usuario")
    session["current_cart"] = None

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
    """Elimina únicamente la sesión en memoria del usuario indicado."""
    normalized_id = _normalized_user_id(user_id)
    if normalized_id is None:
        return
    _sessions.pop(normalized_id, None)


def clear_all_sessions() -> None:
    """Elimina todas las sesiones en memoria.

    Útil al reiniciar pruebas o después de cambios incompatibles de estructura.
    """
    _sessions.clear()


def get_active_session_count() -> int:
    """Cantidad de usuarios con sesión activa en memoria."""
    return len(_sessions)