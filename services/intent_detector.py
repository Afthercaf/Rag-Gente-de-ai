"""
Detecta la intención del mensaje en Python antes de llamar al LLM.
La lógica de flujo vive aquí — el LLM solo genera texto.
"""

import re
import unicodedata

# ══════════════════════════════════════════════════════════════════
# KEYWORDS
# ══════════════════════════════════════════════════════════════════

MENU_KEYWORDS = {
    "menu", "menú", "carta", "opciones", "qué tienen",
    "que tienen", "qué pizzas", "que pizzas", "ver menú",
    "ver menu", "qué hay", "que hay",
}

SALUDO_KEYWORDS = {
    "hola", "buenas", "buenos días", "buenos dias",
    "buenas tardes", "buenas noches", "hey", "qué tal",
    "que tal", "saludos",
}

ORDER_KEYWORDS = {
    "quiero", "dame", "ordena", "pedir", "ordenar",
    "me das", "me puedes dar", "quisiera",
}

# Palabras que indican una PREGUNTA (no una orden)
QUESTION_KEYWORDS = {
    "cuánto", "cuanto", "precio", "cuesta", "costar", "valor",
    "promoción", "promo", "descuento", "horario", "dónde", "donde",
    "ubicación", "ubicacion", "cómo", "como", "cuál", "cual",
    "qué", "que", "por qué", "porque", "para qué", "para que",
    "existe", "tienen", "hay", "ofrecen",
}

NO_EXTRAS_KEYWORDS = {
    "no", "ninguno", "ninguna", "nada", "sin extras",
    "así está bien", "asi esta bien", "está bien", "esta bien",
    "listo", "perfecto", "sin nada", "nada más", "nada mas",
}

# Señales de que el flujo ya terminó (pedido confirmado / ubicación pedida)
FLOW_END_SIGNALS = {
    "📝 pedido:",
    "confirmas tu pedido",
    "ubicación",
    "ubicacion",
    "comparte tu",
    "compartir",
}

# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _normalize(text: str) -> str:
    """Lowercase, sin tildes, sin espacios extra."""
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _norm_set(keywords: set[str]) -> set[str]:
    return {_normalize(k) for k in keywords}


_MENU_NORM    = _norm_set(MENU_KEYWORDS)
_SALUDO_NORM  = _norm_set(SALUDO_KEYWORDS)
_ORDER_NORM   = _norm_set(ORDER_KEYWORDS)
_QUESTION_NORM = _norm_set(QUESTION_KEYWORDS)
_NOEXT_NORM   = _norm_set(NO_EXTRAS_KEYWORDS)
_FLOWEND_NORM = _norm_set(FLOW_END_SIGNALS)


def has_menu_intent(text: str) -> bool:
    n = _normalize(text)
    return any(kw in n for kw in _MENU_NORM)


def has_pizza_name(text: str, pizza_names: list[str]) -> str | None:
    """Retorna el nombre de la pizza encontrada, o None."""
    n = _normalize(text)
    for name in pizza_names:
        if _normalize(name) in n:
            return name
    return None


def is_only_greeting(text: str) -> bool:
    n = _normalize(text)
    words = set(n.split())
    return bool(words & _SALUDO_NORM) and not bool(words & _ORDER_NORM)


def has_order_intent(text: str) -> bool:
    """
    True si el usuario QUIERE ORDENAR (no solo preguntar sobre precios/promos).
    
    Una pregunta NO es una orden, incluso si contiene palabras como "quiero".
    Ejemplo: "¿Cuánto cuesta la pizza?" → False
    Ejemplo: "Quiero una pizza" → True
    """
    n = _normalize(text)
    
    # Si es una pregunta → NO es orden
    if any(kw in n for kw in _QUESTION_NORM):
        return False
    
    # Si no es pregunta y tiene palabras de orden → es orden
    return any(kw in n for kw in _ORDER_NORM)


def is_negative_or_skip(text: str) -> bool:
    """True si el usuario no quiere nada / confirma sin cambios."""
    n = _normalize(text)
    return any(kw in n for kw in _NOEXT_NORM)


def _flow_terminated(assistant_msg: str) -> bool:
    """True si el mensaje del asistente indica que el flujo ya terminó."""
    n = _normalize(assistant_msg)
    return any(signal in n for signal in _FLOWEND_NORM)


def has_previous_order(history: list[dict]) -> str | None:
    """Retorna el producto del último pedido confirmado, o None."""
    for msg in reversed(history):
        assistant_msg = msg.get("assistant", "")
        if "📝 PEDIDO:" in assistant_msg:
            for line in assistant_msg.split("\n"):
                if line.strip().startswith("Producto:"):
                    return line.split(":", 1)[1].strip()
    return None


# ══════════════════════════════════════════════════════════════════
# DETECCIÓN DE FLUJO ACTIVO
# ══════════════════════════════════════════════════════════════════

def _get_flow_start(history: list[dict]) -> int | None:
    """
    Retorna el índice en `history` donde comenzó el flujo activo.

    El flujo se resetea (flow_start = None) cuando el asistente emite
    cualquier señal de fin: 📝 PEDIDO, confirmas tu pedido, ubicación, etc.
    El flujo comienza cuando el asistente pregunta el tamaño sin mencionar
    ingredientes ni extras (es decir, el Paso 1 limpio).
    """
    flow_start = None

    for i, msg in enumerate(history):
        assistant_msg = msg.get("assistant", "")

        # ── Señal de fin → resetear flujo ────────────────────────
        if _flow_terminated(assistant_msg):
            flow_start = None
            continue

        # ── Inicio de nuevo flujo (Paso 1: pregunta de tamaño) ───
        n = assistant_msg.lower()
        is_size_question = (
            "tamaño" in n
            and not any(kw in n for kw in ["incluye", "extra", "pedido", "confirma"])
        )
        if is_size_question:
            flow_start = i

    return flow_start


def get_active_order_step(history: list[dict]) -> int | None:
    """
    Paso actual del flujo basado en cuántas respuestas del usuario
    han ocurrido desde el inicio (conteo determinista).

      1 → asistente preguntó tamaño       — usuario no ha respondido aún
      2 → usuario respondió tamaño        — asistente preguntó ingredientes
      3 → usuario respondió ingredientes  — asistente preguntó extras
      None → usuario respondió extras (→ confirmar) o no hay flujo activo
    """
    flow_start = _get_flow_start(history)
    if flow_start is None:
        return None

    user_replies = sum(
        1 for msg in history[flow_start + 1:]
        if msg.get("user", "").strip()
    )

    return {0: 1, 1: 2, 2: 3}.get(user_replies)  # None si >= 3


def get_active_pizza(history: list[dict]) -> str | None:
    """
    Retorna el nombre de la pizza del flujo activo.
    Busca en los mensajes del asistente desde el inicio del flujo.
    """
    flow_start = _get_flow_start(history)
    if flow_start is None:
        return None

    for msg in history[flow_start:]:
        assistant_msg = msg.get("assistant", "")
        match = re.search(
            r"pizza\s+([A-ZÁ-Úa-záéíóúñ][a-záéíóúñ]+(?:\s+[A-ZÁ-Úa-záéíóúñ][a-záéíóúñ]+)*)",
            assistant_msg,
            re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()

    return None


def _get_user_reply_at(history: list[dict], offset: int) -> str:
    """
    Retorna el mensaje del usuario en la posición `offset`
    contando desde el inicio del flujo activo (0-indexed).

      offset 0 → tamaño elegido
      offset 1 → respuesta de ingredientes
      offset 2 → respuesta de extras
    """
    flow_start = _get_flow_start(history)
    if flow_start is None:
        return ""

    replies = [
        msg.get("user", "").strip()
        for msg in history[flow_start + 1:]
        if msg.get("user", "").strip()
    ]
    return replies[offset] if offset < len(replies) else ""


# ══════════════════════════════════════════════════════════════════
# BUILD DIRECTIVE — punto de entrada principal
# ══════════════════════════════════════════════════════════════════

def build_directive(
    question: str,
    pizza_names: list[str],
    history: list[dict],
) -> str:
    """
    Toda la lógica de decisión vive aquí.
    El LLM solo genera texto — nunca decide el siguiente paso.

    Prioridad:
      0. MENÚ — prioridad absoluta
      1. Flujo activo (pasos 1 → 2 → 3 → confirmar)
      2. Nueva pizza mencionada
      3. Intención de pedir sin pizza
      4. Saludo de cliente frecuente (CASO A)
      5. Información general
    """
    
    print(f"🔍 [DEBUG] build_directive - question: {question}")
    print(f"🔍 [DEBUG] pizza_names: {pizza_names[:5] if pizza_names else []}...")
    print(f"🔍 [DEBUG] history length: {len(history)}")

    # ── 0. MENÚ — prioridad absoluta ─────────────────────────────
    if has_menu_intent(question):
        print("✅ [DEBUG] Caso: MENÚ")
        return (
            "Muestra el menú completo del CONTEXTO. "
            "No menciones pedidos anteriores ni pedidos en curso. "
            "Al final pregunta: '¿Cuál te llama la atención? 🍕'"
        )

    # ── 1. FLUJO ACTIVO ───────────────────────────────────────────
    active_step = get_active_order_step(history)
    print(f"🔍 [DEBUG] active_step: {active_step}")

    if active_step is not None:
        pizza   = get_active_pizza(history) or "la pizza solicitada"
        size    = _get_user_reply_at(history, 0)
        removed = _get_user_reply_at(history, 1)
        print(f"🔍 [DEBUG] Flujo activo - pizza: {pizza}, size: {size}, step: {active_step}")

        # Paso 1 → usuario respondió tamaño, avanzar a ingredientes
        if active_step == 1:
            print("✅ [DEBUG] Caso: FLUJO PASO 1 (ingredientes)")
            return (
                f"El cliente eligió el tamaño '{question}' para la Pizza {pizza}. "
                f"Consulta el CONTEXTO y dile qué ingredientes base incluye esa pizza. "
                f"Luego pregunta si desea quitar alguno. "
                f"Formato exacto: 'La Pizza {pizza} incluye: [ingredientes del CONTEXTO]. ¿Deseas quitar alguno? 🥗'"
            )

        # Paso 2 → usuario respondió ingredientes, avanzar a extras
        if active_step == 2:
            # Si el usuario responde "no" a los ingredientes, es válido (sin cambios)
            print("✅ [DEBUG] Caso: FLUJO PASO 2 (extras)")
            extras_disponibles = "Queso extra, Orilla de queso, Pepperoni extra"
            return (
                f"El cliente respondió '{question}' sobre ingredientes. "
                f"Pizza: {pizza} | Tamaño: {size}. "
                f"Responde EXACTAMENTE con este texto, sin cambiar nada:\n"
                f"'¿Quieres agregar algún extra? Disponibles: {extras_disponibles} ➕'"
            )

        # Paso 3 → usuario respondió extras, generar pedido final
        if active_step == 3:
            print("✅ [DEBUG] Caso: FLUJO PASO 3 (confirmar pedido)")
            extras         = "Ninguno" if is_negative_or_skip(question) else question
            removed_clean  = "Ninguno" if is_negative_or_skip(removed)  else removed

            return (
                f"El cliente terminó de personalizar su pedido. "
                f"Genera el resumen FINAL con EXACTAMENTE este formato, sin agregar nada más. "
                f"Incluye también una línea 'Total:' con el precio calculado según el tamaño y los extras.\n\n"
                f"✅ ¡Perfecto! Tu pedido está listo:\n\n"
                f"📝 PEDIDO:\n"
                f"Cantidad: 1\n"
                f"Producto: Pizza {pizza}\n"
                f"Tamaño: {size}\n"
                f"Extras: {extras}\n"
                f"Ingredientes removidos: {removed_clean}\n\n"
                f"¿Confirmas tu pedido? ✅"
            )

    # ── 3. NUEVA PIZZA MENCIONADA ─────────────────────────────────
    pizza_found = has_pizza_name(question, pizza_names)
    print(f"🔍 [DEBUG] pizza_found: {pizza_found}")
    
    if pizza_found:
        is_question = any(kw in _normalize(question) for kw in _QUESTION_NORM)
        print(f"🔍 [DEBUG] es pregunta: {is_question}")
        
        if is_question:
            print("✅ [DEBUG] Caso: PREGUNTA SOBRE PIZZA (no orden)")
            return (
                f"El cliente preguntó sobre la Pizza {pizza_found}. "
                f"Responde SOLO con la información disponible en el CONTEXTO. "
                f"No inicies un flujo de pedido. "
                f"No incluyas la sección 📝 PEDIDO."
            )
        
        print("✅ [DEBUG] Caso: NUEVA PIZZA - INICIAR FLUJO")
        tamanos_disponibles = "Pequeña, Mediana, Grande"
        return (
            f"El cliente quiere ordenar la Pizza {pizza_found}. "
            f"Responde EXACTAMENTE con este texto, sin cambiar nada:\n"
            f"'¿Qué tamaño deseas? Tenemos: {tamanos_disponibles} 🍕'"
        )

    # ── 4. QUIERE ORDENAR SIN ESPECIFICAR PIZZA ───────────────────
    if has_order_intent(question):
        print("✅ [DEBUG] Caso: ORDENAR SIN PIZZA")
        return (
            "El cliente quiere ordenar pero no dijo qué pizza. "
            "Muestra el menú completo del CONTEXTO. "
            "Al final pregunta: '¿Cuál te llama la atención? 🍕'"
        )

    # ── 5. SALUDO DE CLIENTE FRECUENTE (CASO A) ───────────────────
    # Condiciones estrictas para CASO A:
    # 1. Es solo un saludo (sin palabras de orden)
    # 2. No contiene nombre de pizza
    # 3. No es intención de menú
    # 4. Existe un pedido anterior en el historial
    last_order = has_previous_order(history)
    is_greeting_only = is_only_greeting(question)
    has_no_pizza = has_pizza_name(question, pizza_names) is None
    has_no_menu = not has_menu_intent(question)
    
    print(f"🔍 [DEBUG] CASO A - is_greeting_only: {is_greeting_only}, has_no_pizza: {has_no_pizza}, has_no_menu: {has_no_menu}, last_order: {last_order}")
    
    if is_greeting_only and has_no_pizza and has_no_menu and last_order:
        print("✅ [DEBUG] Caso: SALUDO CON PEDIDO ANTERIOR (CASO A)")
        return (
            f"El cliente saludó. Su último pedido fue: {last_order}. "
            f"Responde EXACTAMENTE con este texto, sin cambiar nada:\n"
            f"'¡Hola! 😊 La última vez pediste {last_order}. ¿Te gustaría ordenar lo mismo o prefieres ver el menú completo?'"
        )

    # ── 6. INFORMACIÓN GENERAL ────────────────────────────────────
    print("✅ [DEBUG] Caso: INFORMACIÓN GENERAL (default)")
    return (
        "Responde con la información disponible en el CONTEXTO. "
        "No incluyas la sección 📝 PEDIDO."
    )