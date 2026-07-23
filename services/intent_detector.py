"""
Detecta la intención del mensaje en Python antes de llamar al LLM.

FLUJO DE UN SOLO PASO (eliminado el paso de "quitar ingredientes"):
1. Cuando el cliente menciona una pizza, se pregunta DIRECTAMENTE
   por extras (mostrando la lista de extras disponibles con precio).
2. No se pregunta, menciona ni ofrece la opción de quitar ingredientes.
3. No se guarda ni muestra "Ingredientes removidos" en el resumen final.
4. El resumen final contiene: Cantidad, Producto, Tamaño, Extras, Observaciones, Total.
"""

import re
import unicodedata
from typing import Optional, List, Tuple

MENU_KEYWORDS = {
    "menu", "menú", "carta", "opciones", "qué tienen",
    "que tienen", "qué pizzas", "que pizzas", "ver menú",
    "ver menu", "qué hay", "que hay", "muestra", "enséñame",
    "enseñame", "mostrar", "ver",
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
QUESTION_KEYWORDS = {
    "cuánto", "cuanto", "precio", "cuesta", "costar", "valor",
    "promoción", "promo", "descuento", "horario", "dónde", "donde",
    "ubicación", "ubicacion", "cómo", "como", "cuál", "cual",
    "qué", "que", "por qué", "porque", "para qué", "para que",
    "existe", "tienen", "hay", "ofrecen",
}
CANCEL_KEYWORDS = {
    "cancelar", "cancela", "cancelar pedido", "deja", "olvida", "borra",
    "quitarlo", "cancelar el pedido", "cancela el pedido", "cancela pedido",
    "no quiero nada", "mejor no pido", "mejor no",
}
INJECTION_PATTERNS = (
    r"\b(?:dame|muestra|revela|explica|imprime)\b.*\b(?:prompt|instrucciones internas|base de datos|estructura|schema|tablas|contexto interno)\b",
    r"\b(?:actua|actúa)\s+como\b",
    r"\b(?:ignora|omite|olvida)\b.*\b(?:instrucciones|reglas|prompt)\b",
    r"\b(?:system prompt|developer message|cadena de pensamiento)\b",
    r"\b(?:cuanto es|cuánto es|resuelve|calcula)\b.*\b(?:\d+\s*[+\-*/×÷]\s*\d+|raiz|raíz|potencia|logaritmo|seno|coseno|integral|derivada)\b",
    r"\b(?:escribe|crea|genera|haz un)\b.*\b(?:programa|código|codigo|script|función|funcion|clase|algoritmo)\b.*\b(?:php|python|java|javascript|html|css|sql|rust|go|ruby|c\+\+|c#)\b",
    r"\b(?:hola mundo|hello world|print\s*\(|console\.log)\b",
)
PIZZA_GENERIC_PATTERN = re.compile(
    r"\bpizzas?\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+){0,2})\b", re.IGNORECASE,
)
NO_EXTRAS_KEYWORDS = {
    "no", "ninguno", "ninguna", "nada", "sin extras",
    "así está bien", "asi esta bien", "está bien", "esta bien",
    "listo", "perfecto", "sin nada", "nada más", "nada mas",
    "no quiero", "no gracias", "mejor no", "cancelar", "cancela",
    "no me gusta", "no me agrada", "cambiar", "otra",
}
PURE_AFFIRMATION_KEYWORDS = {
    "si", "sí", "claro", "va", "dale", "sale", "obvio",
    "por favor", "quiero extras", "si quiero", "sí quiero",
    "agregale", "agrégale", "ponle",
}
FLOW_END_SIGNALS = {
    "📝 pedido:", "confirmas tu pedido", "ubicación", "ubicacion",
    "comparte tu", "compartir",
}
FLOW_END_EXCLUSIVE_PHRASE = "te llama la atención"
REPEAT_OFFER_SIGNAL = "ordenar lo mismo"
WHICH_EXTRA_SIGNAL = "cuál extra te gustaría agregar"
_PRICE_PATTERN = re.compile(r"\$\s*(\d+(?:[.,]\d{1,2})?)")
LITERAL_RESPONSE_PREFIX = "::LITERAL_RESPONSE::"


def _normalize(text: str) -> str:
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def _norm_set(keywords: set[str]) -> set[str]:
    return {_normalize(k) for k in keywords}

_MENU_NORM      = _norm_set(MENU_KEYWORDS)
_SALUDO_NORM    = _norm_set(SALUDO_KEYWORDS)
_ORDER_NORM     = _norm_set(ORDER_KEYWORDS)
_QUESTION_NORM  = _norm_set(QUESTION_KEYWORDS)
_NOEXT_NORM     = _norm_set(NO_EXTRAS_KEYWORDS)
_FLOWEND_NORM   = _norm_set(FLOW_END_SIGNALS)
_PUREAFFIRM_NORM = _norm_set(PURE_AFFIRMATION_KEYWORDS)
_CANCEL_NORM    = _norm_set(CANCEL_KEYWORDS)
_NOEXT_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in _NOEXT_NORM) + r")\b"
)


def has_menu_intent(text: str) -> bool:
    n = _normalize(text)
    return any(re.search(r'\b' + re.escape(kw) + r'\b', n) for kw in _MENU_NORM)

def has_pizza_name(text: str, pizza_names: list[str]) -> str | None:
    n = _normalize(text)
    # Primero buscar coincidencias precedidas por "pizza" (más específico)
    pizza_prefixed = []
    for name in pizza_names:
        if re.search(r'\bpizza\s+' + re.escape(_normalize(name)) + r'\b', n):
            pizza_prefixed.append(name)
    if pizza_prefixed:
        # Si hay varias, preferir la más larga
        return max(pizza_prefixed, key=len)
    
    # Fallback: ordenar por longitud descendente
    sorted_names = sorted(pizza_names, key=len, reverse=True)
    for name in sorted_names:
        if re.search(r'\b' + re.escape(_normalize(name)) + r'\b', n):
            return name
    return None

def is_only_greeting(text: str) -> bool:
    n = _normalize(text)
    words = set(n.split())
    return bool(words & _SALUDO_NORM) and not bool(words & _ORDER_NORM)

def has_order_intent(text: str) -> bool:
    n = _normalize(text)
    if any(re.search(r'\b' + re.escape(kw) + r'\b', n) for kw in _QUESTION_NORM):
        return False
    return any(re.search(r'\b' + re.escape(kw) + r'\b', n) for kw in _ORDER_NORM)

def is_prompt_injection(text: str) -> bool:
    n = _normalize(text)
    return any(re.search(pattern, n, re.IGNORECASE) for pattern in INJECTION_PATTERNS)

def is_explicit_negated_order(text: str) -> bool:
    n = _normalize(text)
    return bool(re.search(
        r"\b(?:no|nunca|tampoco)\s+(?:quiero|quisiera|deseo|voy a pedir|"
        r"pedire|ordenare|me des)\b.*\bpizza\b", n,
    ))

def has_cancel_intent(text: str) -> bool:
    n = _normalize(text)
    return any(kw in n for kw in _CANCEL_NORM)

def extract_unknown_pizza(text: str, pizza_names: list[str]) -> str | None:
    """Detecta pizzas inexistentes aceptando plurales naturales."""
    n = _normalize(text)
    known = {_normalize(name).removeprefix("pizza ").strip() for name in pizza_names}

    for match in PIZZA_GENERIC_PATTERN.finditer(n):
        candidate = match.group(1).strip()
        candidate = re.split(
            r"\b(?:con|sin|y|de|para|por)\b",
            candidate,
            maxsplit=1,
        )[0].strip()

        if not candidate:
            continue

        variants = {candidate}
        if candidate.endswith("es"):
            variants.add(candidate[:-2])
        if candidate.endswith("s"):
            variants.add(candidate[:-1])

        if variants & known:
            continue

        return candidate.title()

    return None

def extract_unknown_extra(text: str, extras_context: str) -> str | None:
    if not extras_context:
        return None
    n = _normalize(text)
    if is_no_in_order_flow(text):
        return None
    extras_lower = _normalize(extras_context)
    words = re.findall(r"\b[a-záéíóúñ]{4,}\b", n)
    stop_words = {"quiero", "agregar", "extra", "con", "y", "por", "favor", "ademas", "tambien"}
    for word in words:
        if word in stop_words:
            continue
        if word not in extras_lower:
            if word not in _normalize(" ".join(NO_EXTRAS_KEYWORDS)):
                return word
    return None

def extract_unknown_promo(text: str, promos_text: str) -> bool:
    if not promos_text:
        n = _normalize(text)
        if re.search(r"\bpromo", n) or re.search(r"\bdescuento", n) or re.search(r"\boferta", n):
            return True
        return False
    n = _normalize(text)
    promos_lower = _normalize(promos_text)
    promo_patterns = re.findall(
        r"\b(?:promo|promoción|promocion|descuento|oferta|2x1|gratis)\b\s*(.*?)(?:\b(?:y|para|por)\b|$)", n
    )
    for promo_text in promo_patterns:
        promo_text = promo_text.strip()
        if promo_text and promo_text not in promos_lower:
            return True
    return False

def _build_price_quote(question: str, pizza_names: list[str], context: str, extras_context: str) -> str | None:
    n = _normalize(question)
    if not any(k in n for k in ("cuanto", "precio", "cuesta", "costaria", "valor")):
        return None
    pizza = has_pizza_name(question, pizza_names)
    if not pizza:
        return None
    base = _menu_pizza_price(pizza, context)
    if base is None:
        return LITERAL_RESPONSE_PREFIX + f"No pude consultar el precio de la Pizza {pizza} en este momento."
    requested = _find_requested_extras(question, extras_context)
    extras_total = sum(float(e["price"]) for e in requested)
    extras_found = [e["name"] for e in requested]
    total = base + extras_total
    if extras_found:
        detail = ", ".join(extras_found)
        return LITERAL_RESPONSE_PREFIX + (
            f"La Pizza {pizza} cuesta ${base:.2f} MXN. Con {detail}, el total es ${total:.2f} MXN."
        )
    return LITERAL_RESPONSE_PREFIX + f"La Pizza {pizza} cuesta ${base:.2f} MXN."

def _build_total_quote(history: list[dict], pizza_names: list[str], context: str, extras_context: str) -> str | None:
    flow_start = _get_flow_start(history, pizza_names)
    if flow_start is None:
        return None
    pizza = get_active_pizza(history, pizza_names)
    if not pizza:
        return None
    base = _menu_pizza_price(pizza, context)
    if base is None:
        return LITERAL_RESPONSE_PREFIX + (
            f"Llevas Pizza {pizza}. No pude calcular el total exacto en este momento, "
            f"pero puedo ayudarte a terminar tu pedido."
        )
    replies = _filter_flow_replies(history, flow_start)
    extras_answer = replies[0] if replies else ""
    if is_no_in_order_flow(extras_answer) or not extras_answer:
        return LITERAL_RESPONSE_PREFIX + (
            f"Llevas Pizza {pizza} (${base:.2f} MXN) sin extras hasta ahora. ¿Quieres agregar algún extra? ➕"
        )
    extras_total, extras_found = _sum_requested_extras(extras_answer, extras_context)
    total = base + extras_total
    if extras_found:
        detail = ", ".join(extras_found)
        return LITERAL_RESPONSE_PREFIX + (
            f"Tu pedido hasta ahora:\n"
            f"• Pizza {pizza} — ${base:.2f}\n"
            f"• Extras: {detail} — ${extras_total:.2f}\n"
            f"Total parcial: ${total:.2f} MXN\n\n"
            f"¿Quieres agregar algo más o confirmar? ✅"
        )
    return LITERAL_RESPONSE_PREFIX + (
        f"Llevas Pizza {pizza} (${base:.2f} MXN). ¿Quieres agregar algún extra? ➕"
    )

def _is_drink_question(text: str) -> bool:
    normalized = _normalize(text)
    return ("?" in text and bool(re.search(
        r"\b(refresco|refrescos|bebida|bebidas|coca[ -]?cola)\b", normalized
    )))

def _build_drink_response() -> str:
    try:
        from services.menu_formatter import MenuFormatter
        menu = MenuFormatter().format()
        beverage_lines = [
            line.strip() for line in menu.splitlines()
            if line.strip().startswith("•")
            and any(word in _normalize(line) for word in ("coca", "refresco", "bebida"))
        ]
    except Exception:
        beverage_lines = []
    if beverage_lines:
        return LITERAL_RESPONSE_PREFIX + (
            "Las bebidas se agregan por separado a la pizza:\n"
            + "\n".join(beverage_lines)
            + "\n\n¿Quieres agregar alguna a tu pedido?"
        )
    return LITERAL_RESPONSE_PREFIX + (
        "No tengo registrada una pizza que incluya refresco. "
        "Las bebidas se pueden agregar por separado al pedido."
    )

def _extract_multi_pizza_items(text: str, pizza_names: list[str]) -> list[tuple[str, int]]:
    normalized = _normalize(text)
    quantities = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6}
    items: list[tuple[str, int]] = []
    for name in sorted(pizza_names, key=len, reverse=True):
        normalized_name = _normalize(name)
        pattern = re.compile(
            rf"(?:^|[,;]|\by\b)\s*(?:(\d+)|({'|'.join(quantities)}))?\s*"
            rf"(?:pizzas?\s*)?(?:pizza\s*)?{re.escape(normalized_name)}\b"
        )
        match = pattern.search(normalized)
        if not match:
            continue
        quantity = int(match.group(1)) if match.group(1) else quantities.get(match.group(2), 1)
        items.append((name, quantity))
    return items

def _build_multi_pizza_summary(items: list[tuple[str, int]], context: str) -> str:
    lines = ["✅ ¡Perfecto! Registré cada pizza de tu pedido:", "", "📝 PEDIDO:", "Productos:"]
    total_quantity = 0
    total_price = 0.0
    prices_available = True
    for name, quantity in items:
        unit_price = _extract_price_near(context, name)
        total_quantity += quantity
        if unit_price is None:
            prices_available = False
            lines.append(f"• {quantity} × Pizza {name} — precio no disponible")
        else:
            total_price += unit_price * quantity
            lines.append(f"• {quantity} × Pizza {name} — ${unit_price:.2f} c/u")
    lines.append(f"Cantidad: {total_quantity}")
    lines.append("Extras: Ninguno")
    lines.append(f"Total: ${total_price:.2f}" if prices_available else "Total: [precio no disponible]")
    lines.append("")
    lines.append("¿Confirmas tu pedido? ✅")
    return LITERAL_RESPONSE_PREFIX + "\n".join(lines)

def is_negative_or_skip(text: str) -> bool:
    n = _normalize(text)
    return any(kw in n for kw in _NOEXT_NORM)

def is_no_in_order_flow(text: str) -> bool:
    n = _normalize(text)
    return bool(_NOEXT_PATTERN.search(n))

def is_pure_affirmation(text: str) -> bool:
    n = _normalize(text)
    words = set(re.findall(r"\w+", n))
    return bool(words & _PUREAFFIRM_NORM)

def _flow_terminated(assistant_msg: str) -> bool:
    n = _normalize(assistant_msg)
    signals = _FLOWEND_NORM | {_normalize(FLOW_END_EXCLUSIVE_PHRASE)}
    return any(signal in n for signal in signals)

def is_pending_repeat_offer(history: list[dict]) -> bool:
    if not history:
        return False
    last_assistant = history[-1].get("assistant", "")
    return _normalize(REPEAT_OFFER_SIGNAL) in _normalize(last_assistant)

def has_previous_order(history: list[dict]) -> str | None:
    for msg in reversed(history):
        assistant_msg = msg.get("assistant", "")
        if "📝 PEDIDO:" in assistant_msg:
            for line in assistant_msg.split("\n"):
                if line.strip().startswith("Producto:"):
                    return line.split(":", 1)[1].strip()
    return None

def _detected_pizza_change(text: str, pizza_names: list[str] | None = None,
                           require_explicit: bool = False) -> bool:
    n = text.lower()
    if re.search(r'quiero\s+cambiar', n) or re.search(r'cambiarla', n) or re.search(r'cambiármela', n):
        return True
    pizza_word_patterns = [
        r'no\s+quiero\s+(?:la\s+)?pizza\s+([A-Za-záéíóúñ]+)',
        r'quiero\s+(?:la\s+)?pizza\s+([A-Za-záéíóúñ]+)',
        r'cambiar\s+(?:la\s+)?pizza\s+([A-Za-záéíóúñ]+)',
        r'otra\s+pizza\s+([A-Za-záéíóúñ]+)',
        r'mejor\s+(?:la\s+)?pizza\s+([A-Za-záéíóúñ]+)',
    ]
    for pattern in pizza_word_patterns:
        if re.search(pattern, n):
            return True
    if not require_explicit and pizza_names and has_pizza_name(text, pizza_names):
        return True
    return False

def _get_pizza_names_from_history(history: list[dict]) -> list[str]:
    names = set()
    for msg in history:
        for role in ("user", "assistant"):
            text = msg.get(role, "")
            matches = re.findall(
                r'(?:pizza|🍕)\s+([A-ZÁ-Ú][a-záéíóúñ]+(?:\s+[A-ZÁ-Ú][a-záéíóúñ]+)*)',
                text, re.IGNORECASE
            )
            names.update(matches)
    return list(names)

def _extract_price_near(text: str, target_name: str) -> float | None:
    if not text or not target_name:
        return None
    target_norm = _normalize(target_name)
    pizza_name = re.sub(r"^pizza\s+", "", target_norm).strip()
    if not pizza_name:
        return None
    pizza_pattern = re.compile(rf"\bpizza\s+{re.escape(pizza_name)}\b")
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if pizza_pattern.search(_normalize(line)):
            match = _PRICE_PATTERN.search(line)
            if match:
                return float(match.group(1).replace(",", "."))
            for next_line in lines[i + 1: i + 4]:
                next_line_norm = _normalize(next_line)
                if re.search(r"^\s*pizza\s+", next_line_norm) or re.search(
                    r"\b(extras?|adicionales?|bebidas?|refrescos?)\b", next_line_norm
                ):
                    break
                match = _PRICE_PATTERN.search(next_line)
                if match:
                    return float(match.group(1).replace(",", "."))
            break
    return None

def _parse_priced_items(block: str) -> list[tuple[str, float]]:
    items: list[tuple[str, float]] = []
    if not block:
        return items
    # Formato: "Nombre: $precio" o "• Nombre — $precio" o "Nombre $precio"
    # El patrón captura el nombre (grupo 1) y el precio (grupo 2)
    pattern = re.compile(r"^[\s•\-\*\u2022\u2023\u25e6\u2043\u2219]+([^$:]+?)\s*[:\-–—]?\s*\$\s*(\d+(?:[.,]\d{1,2})?)")
    for line in block.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = pattern.search(line)
        if match:
            name = match.group(1).strip()
            # Limpiar caracteres residuales de formato (viñetas, guiones, etc.)
            name = re.sub(r"^[\s•\-\*\u2022\u2023\u25e6\u2043\u2219]+", "", name)
            name = re.sub(r"[\s•\-\*\u2022\u2023\u25e6\u2043\u2219]+$", "", name)
            name = name.strip()
            if name:
                items.append((name, float(match.group(2).replace(",", "."))))
    return items

# ═══════════════════════════════════════════════════════════════════
# UNIFIED ORDER PARSER — Extrae TODOS los ítems (pizza, extras, bebidas)
# de un mensaje único y devuelve datos estructurados con precios.
# ═══════════════════════════════════════════════════════════════════

class ParsedOrder:
    """Resultado estructurado del parsing de un pedido completo."""
    def __init__(self):
        self.pizza_name: str = ""
        self.pizza_price: float | None = None
        self.extras: list[tuple[str, float]] = []  # [(nombre, precio)]
        self.beverages: list[tuple[str, float]] = []  # [(nombre, precio)]
        self.observations: str = ""
        self.total_price: float | None = None
    
    @property
    def extras_display(self) -> str:
        """String para mostrar en 'Extras:'."""
        if not self.extras:
            return "Ninguno"
        return ", ".join(name for name, _ in self.extras)
    
    @property
    def extras_total(self) -> float:
        return sum(price for _, price in self.extras)
    
    @property
    def beverages_total(self) -> float:
        return sum(price for _, price in self.beverages)
    
    @property
    def has_unresolved_items(self) -> bool:
        """True si algún ítem no tiene precio."""
        if self.pizza_price is None:
            return True
        for _, price in self.extras:
            if price is None:
                return True
        for _, price in self.beverages:
            if price is None:
                return True
        return False

    @property
    def has_all_prices(self) -> bool:
        """True si todos los ítems tienen precio resuelto."""
        return not self.has_unresolved_items


def parse_order_from_message(message: str, pizza_names: list[str], extras_context: str, context: str) -> ParsedOrder:
    """
    Parsea un mensaje completo del cliente y extrae:
    - Pizza (nombre + precio)
    - Extras (lista con precios)
    - Bebidas (lista con precios)
    - Observaciones (texto libre no reconocido)
    
    Usa EXCLUSIVAMENTE los precios del contexto/menu (extras_context, context).
    Nunca inventa precios.
    """
    from services.rag_service import get_menu_context
    
    result = ParsedOrder()
    msg_norm = _normalize(message)
    
    # 1) Detectar pizza
    pizza_found = has_pizza_name(message, pizza_names)
    if pizza_found:
        result.pizza_name = pizza_found
        # Buscar precio en context o menu
        result.pizza_price = _extract_price_near(context, pizza_found)
        if result.pizza_price is None:
            menu_ctx = get_menu_context()
            result.pizza_price = _extract_price_near(menu_ctx, pizza_found)
    
    # Preparar texto para búsqueda de extras/bebidas: remover el nombre de la pizza
    # para evitar falsos positivos (ej. "Pepperoni" es pizza y extra)
    text_for_extras = message
    if pizza_found:
        # Remover la pizza y palabras conectoras comunes
        pizza_norm = _normalize(pizza_found)
        # Patrones para remover: "pizza X", "X", "con X", "y X"
        text_for_extras = re.sub(
            rf"\b(?:pizza\s+)?{re.escape(pizza_norm)}\b",
            " ",
            msg_norm,
            flags=re.IGNORECASE
        )
        # También remover conectores típicos, PERO no "de" porque forma parte
        # de nombres como "orilla de queso", "queso de cabra", etc.
        text_for_extras = re.sub(r"\b(con|y|sin|para|por)\b", " ", text_for_extras)
        text_for_extras = re.sub(r"\s+", " ", text_for_extras).strip()
    else:
        text_for_extras = _normalize(message)
    
    # 2) Extraer extras del mensaje LIMPIO (sin el nombre de la pizza)
    extras_total, found_extras = _sum_requested_extras(text_for_extras, extras_context)
    for name in found_extras:
        # Buscar precio del extra
        for ename, eprice in _parse_priced_items(extras_context):
            if _normalize(ename) == _normalize(name):
                result.extras.append((ename, eprice))
                break
    
    # 3) Extraer bebidas del mensaje ORIGINAL (las bebidas no colisionan con pizzas)
    beverage_patterns = [
        r"\b(coca[-\s]?cola|refresco|bebida)\b",
    ]
    has_beverage = any(re.search(p, message, re.IGNORECASE) for p in beverage_patterns)
    
    if has_beverage:
        # La única bebida del menú es Coca-Cola 1.35L a $45.00
        bev_price = None
        for line in context.split("\n"):
            line_lower = _normalize(line)
            if ("coca" in line_lower or "refresco" in line_lower or "bebida" in line_lower) and _PRICE_PATTERN.search(line):
                m = _PRICE_PATTERN.search(line)
                if m:
                    bev_price = float(m.group(1).replace(",", "."))
                    break
        if bev_price is None:
            menu_ctx = get_menu_context()
            for line in menu_ctx.split("\n"):
                line_lower = _normalize(line)
                if ("coca" in line_lower or "refresco" in line_lower or "bebida" in line_lower) and _PRICE_PATTERN.search(line):
                    m = _PRICE_PATTERN.search(line)
                    if m:
                        bev_price = float(m.group(1).replace(",", "."))
                        break
        if bev_price is None:
            bev_price = 45.0
        
        result.beverages.append(("Coca-Cola 1.35L", bev_price))
    
    # 4) Extraer observaciones (texto libre que no sea pizza/extra/bebida)
    result.observations = _extract_observations(message, extras_context)
    
    # 5) Calcular total si todos los precios están disponibles
    if result.pizza_price is not None:
        result.total_price = result.pizza_price + result.extras_total + result.beverages_total
    
    return result


def _sum_requested_extras(extra_answer: str, extras_context: str) -> tuple[float, list[str]]:
    if not extra_answer or not extras_context:
        return 0.0, []
    answer_norm = _normalize(extra_answer)
    total = 0.0
    found: list[str] = []
    for name, price in _parse_priced_items(extras_context):
        if _normalize(name) in answer_norm:
            total += price
            found.append(name)
    return total, found


def _extract_observations(extra_answer: str, extras_context: str) -> str:
    if not extra_answer or is_no_in_order_flow(extra_answer):
        return ""
    answer_norm = _normalize(extra_answer)
    for name, _price in _parse_priced_items(extras_context):
        n = _normalize(name)
        if n and n in answer_norm:
            answer_norm = answer_norm.replace(n, " ")
    answer_norm = re.sub(
        r"\b(y|con|por favor|quiero|agregar|extra|ademas|adicional|tambien|también)\b",
        " ", answer_norm,
    )
    answer_norm = re.sub(r"\s+", " ", answer_norm).strip(" .,-")
    if len(answer_norm) >= 3:
        return extra_answer.strip()
    return ""

def _compute_total(pizza: str, extras_answer: str, extras_context: str, context: str) -> str:
    print(f"  [DEBUG _compute_total] pizza={pizza}, extras_answer='{extras_answer}'")
    print(f"  [DEBUG _compute_total] context length={len(context)}, first 100 chars: {context[:100]}")
    
    pizza_price = _extract_price_near(context, pizza)
    print(f"  [DEBUG _compute_total] pizza_price={pizza_price}")
    
    if pizza_price is None:
        try:
            from core.state import state
            from utils.constants import TOP_K
            docs = state["db"].similarity_search(pizza, k=TOP_K)
            pizza_context = "\n".join(doc.page_content for doc in docs)
            pizza_price = _extract_price_near(pizza_context, pizza)
            print(f"  [DEBUG _compute_total] pizza_price from DB={pizza_price}")
        except Exception as exc:
            print(f"  [DEBUG _compute_total] DB search failed: {exc}")

    # Calcular extras
    if is_no_in_order_flow(extras_answer):
        extras_total, extras_resolved = 0.0, True
    else:
        extras_total, extras_found = _sum_requested_extras(extras_answer, extras_context)
        extras_resolved = bool(extras_found) or is_no_in_order_flow(extras_answer)
        print(f"  [DEBUG _compute_total] extras_total={extras_total}, extras_found={extras_found}")

    # Calcular bebidas del mensaje del cliente
    beverage_total = 0.0
    beverage_pattern = re.compile(r"\b(coca[-\s]?cola|refresco|bebida)\b", re.IGNORECASE)
    beverage_match = beverage_pattern.search(extras_answer)
    print(f"  [DEBUG _compute_total] beverage_match={beverage_match}")
    
    if beverage_match:
        # Buscar precio de bebida en el contexto (no usa _extract_price_near porque busca "pizza <nombre>")
        beverage_price = None
        for line in context.split("\n"):
            line_lower = _normalize(line)
            if ("coca" in line_lower or "refresco" in line_lower or "bebida" in line_lower) and _PRICE_PATTERN.search(line):
                m = _PRICE_PATTERN.search(line)
                if m:
                    beverage_price = float(m.group(1).replace(",", "."))
                    print(f"  [DEBUG _compute_total] Found beverage price: {beverage_price} in line: {line}")
                    break
        if beverage_price is None:
            beverage_price = 45.0  # Precio estándar del menú si no se encuentra
            print(f"  [DEBUG _compute_total] Using default beverage price: {beverage_price}")
        beverage_total = beverage_price

    total = pizza_price + extras_total + beverage_total if pizza_price is not None else None
    print(f"  [DEBUG _compute_total] final total={total}")
    
    if total is not None:
        return f"${total:.2f}"
    return "[precio no disponible]"

def _extract_quantity(history: list[dict], pizza_names: list[str] | None = None) -> int:
    flow_start = _get_flow_start(history, pizza_names)
    if flow_start is None:
        return 1
    candidate_msgs = []
    if flow_start > 0:
        candidate_msgs.append(history[flow_start - 1].get("user", ""))
    candidate_msgs.append(history[flow_start].get("user", ""))
    if flow_start > 0:
        candidate_msgs.append(history[flow_start - 1].get("assistant", ""))
    full_text = " ".join(candidate_msgs)
    m = re.search(r'(\d+)\s*(?:pizza|pieza|orden|órden)', full_text, re.IGNORECASE)
    if m:
        return max(1, int(m.group(1)))
    full_lower = full_text.lower()
    if re.search(r'\bun\s+par\b|\bpar\s+de\b', full_lower):
        return 2
    if re.search(r'\btres\b', full_lower) and 'pizza' in full_lower:
        return 3
    if re.search(r'\bdos\b', full_lower) and 'pizza' in full_lower:
        return 2
    return 1

# ── DETECCIÓN DE FLUJO ACTIVO ──────────────────────────────────

def _get_flow_start(history: list[dict], pizza_names: list[str] | None = None) -> int | None:
    """
    FLUJO DE UN SOLO PASO: la señal de inicio es "extras disponibles para tu"
    en el mensaje del asistente (cuando confirma la pizza y ofrece extras).
    """
    flow_start = None
    for i, msg in enumerate(history):
        user_msg = msg.get("user", "")
        assistant_msg = msg.get("assistant", "")
        if is_only_greeting(user_msg):
            flow_start = None
            continue
        if _flow_terminated(assistant_msg) or _flow_terminated(user_msg):
            flow_start = None
            continue
        if has_menu_intent(user_msg) and not is_negative_or_skip(user_msg):
            flow_start = None
            continue
        is_flow_start_turn = ("extras disponibles para tu" in assistant_msg.lower())
        if pizza_names and not is_flow_start_turn and _detected_pizza_change(user_msg, pizza_names):
            flow_start = None
            continue
        if is_flow_start_turn:
            flow_start = i
    return flow_start

def _filter_flow_replies(history: list[dict], flow_start: int) -> list[str]:
    replies = []
    skip_next = False
    for msg in history[flow_start + 1:]:
        user_msg = msg.get("user", "").strip()
        assistant_msg = msg.get("assistant", "")
        if skip_next:
            skip_next = False
            continue
        if not user_msg:
            continue
        if _normalize(REPEAT_OFFER_SIGNAL) in _normalize(assistant_msg):
            skip_next = True
            continue
        if _normalize(WHICH_EXTRA_SIGNAL) in _normalize(assistant_msg):
            continue
        replies.append(user_msg)
    return replies

def _get_user_reply_at(history: list[dict], offset: int) -> str:
    flow_start = _get_flow_start(history)
    if flow_start is None:
        return ""
    replies = _filter_flow_replies(history, flow_start)
    return replies[offset] if offset < len(replies) else ""

def get_active_pizza(history: list[dict], pizza_names: list[str] | None = None) -> str | None:
    flow_start = _get_flow_start(history, pizza_names)
    if flow_start is None:
        return None
    flow_start_msg = history[flow_start]
    previous_msg = history[flow_start - 1] if flow_start > 0 else None
    if pizza_names:
        for role in ("user", "assistant"):
            found = has_pizza_name(flow_start_msg.get(role, ""), pizza_names)
            if found:
                return found
    if pizza_names and previous_msg:
        for role in ("user", "assistant"):
            found = has_pizza_name(previous_msg.get(role, ""), pizza_names)
            if found:
                return found
    pattern = re.compile(
        r"pizza\s+([A-ZÁ-Úa-záéíóúñ][a-záéíóúñ]+(?:\s+[A-ZÁ-Úa-záéíóúñ][a-záéíóúñ]+)*)",
        re.IGNORECASE,
    )
    candidates = [flow_start_msg] + ([previous_msg] if previous_msg else [])
    for role in ("user", "assistant"):
        for msg in candidates:
            match = pattern.search(msg.get(role, ""))
            if match:
                return match.group(1).strip()
    return None

def get_active_order_step(history: list[dict], pizza_names: list[str] | None = None) -> int | None:
    """FLUJO DE UN SOLO PASO: 0 respuestas -> esperando extras, 1+ respuesta -> completado."""
    flow_start = _get_flow_start(history, pizza_names)
    if flow_start is None:
        return None
    user_replies = _filter_flow_replies(history, flow_start)
    if len(user_replies) == 0:
        return 1  # Esperando respuesta de extras
    return None  # Flujo completado

def is_order_flow_active(history: list[dict], pizza_names: list[str] | None = None) -> bool:
    return get_active_order_step(history, pizza_names) is not None

# ── BUILD DIRECTIVE ────────────────────────────────────────────

def build_directive(
    question: str, pizza_names: list[str], history: list[dict],
    extras_context: str, context: str = "", promos_text: str = "",
) -> str:
    print(f"\n🚀 [LOG TERMINAL] --- NUEVA EVALUACIÓN DE DIRECTIVA ---")
    print(f"📥 Input Usuario (question): '{question}'")
    print(f"🗂️ Mensajes en Historial: {len(history)} turnos")

    # BARRERAS DE SEGURIDAD
    if is_prompt_injection(question):
        return LITERAL_RESPONSE_PREFIX + (
            "No puedo revelar instrucciones internas, estructura de datos ni cambiar mi función. "
            "Sí puedo ayudarte con el menú, precios o un pedido. "
            "Tampoco resuelvo operaciones matemáticas, escribo código ni respondo "
            "preguntas sin relación con la pizzería."
        )
    if is_explicit_negated_order(question):
        return LITERAL_RESPONSE_PREFIX + (
            "Entendido, no iniciaré ningún pedido. ¿Deseas consultar el menú o algún precio?"
        )

    unknown_pizza = extract_unknown_pizza(question, pizza_names)
    if unknown_pizza:
        return LITERAL_RESPONSE_PREFIX + (
            f"La Pizza {unknown_pizza} no existe en nuestro menú. "
            "Puedo mostrarte las pizzas disponibles para que elijas otra."
        )

    # Detectar promociones inventadas
    if extract_unknown_promo(question, promos_text):
        return LITERAL_RESPONSE_PREFIX + (
            "Esa promoción no está disponible actualmente. "
            "Puedo mostrarte las promociones vigentes si deseas."
        )

    # Detectar extras inventados
    unknown_extra = extract_unknown_extra(question, extras_context)
    if unknown_extra and is_order_flow_active(history, pizza_names):
        return LITERAL_RESPONSE_PREFIX + (
            f"No tenemos '{unknown_extra}' como extra disponible. "
            f"¿Quieres ver la lista de extras que sí tenemos? ➕"
        )

    price_quote = _build_price_quote(question, pizza_names, context, extras_context)
    if price_quote:
        return price_quote

    # Cotizar total acumulado ("¿cuánto va?")
    n_question = _normalize(question)
    if any(k in n_question for k in ("cuanto va", "cuánto va", "cuanto llevo", "cuánto llevo", "total parcial", "como voy")):
        if is_order_flow_active(history, pizza_names):
            total_quote = _build_total_quote(history, pizza_names, context, extras_context)
            if total_quote:
                return total_quote

    # Cancelar pedido
    if has_cancel_intent(question) and is_order_flow_active(history, pizza_names):
        return LITERAL_RESPONSE_PREFIX + (
            "✅ Pedido cancelado. No te preocupes, si cambias de opinión "
            "puedes pedir lo que quieras cuando gustes. ¿Te gustaría ver el menú? 🍕"
        )

    # RESPUESTA A OFERTA DE REPETIR PEDIDO
    if len(history) >= 1:
        last_assistant = history[-1].get("assistant", "")
        if _normalize(REPEAT_OFFER_SIGNAL) in _normalize(last_assistant):
            last_order = has_previous_order(history)
            if len(history) >= 2:
                prev_user = history[-2].get("user", "").lower()
                if "no" in prev_user or "sí" in prev_user or "si" in prev_user:
                    pass
                else:
                    if is_negative_or_skip(question) and not has_pizza_name(question, pizza_names):
                        return (
                            "El cliente NO quiere repetir su pedido anterior. "
                            "Muestra el menú completo del CONTEXTO. "
                            "Al final pregunta: '¿Cuál te llama la atención? 🍕'"
                        )
                    pizza_found = has_pizza_name(question, pizza_names)
                    if pizza_found:
                        return (
                            f"El cliente quiere ordenar la Pizza {pizza_found} (tamaño Grande). "
                            f"Consulta el CONTEXTO e inicia el flujo de pedido preguntando "
                            f"directamente por los extras disponibles."
                        )
                    nombre_pizza = last_order or "tu pizza anterior"
                    return (
                        f"El cliente quiere repetir su pedido anterior: {nombre_pizza}. "
                        f"Inicia el flujo de pedido preguntando directamente por los extras."
                    )

    # SALUDO
    if is_only_greeting(question) and not has_pizza_name(question, pizza_names) and not has_menu_intent(question):
        last_order = has_previous_order(history)
        if last_order:
            return (
                f"El cliente saludó. Su último pedido fue: {last_order}. "
                f"Responde: '¡Hola! 😊 La última vez pediste {last_order}. "
                f"¿Te gustaría ordenar lo mismo o prefieres ver el menú completo?'"
            )
        else:
            return LITERAL_RESPONSE_PREFIX + (
                "¡Hola! 😊 Soy el asistente de la pizzería. "
                "Puedo mostrarte el menú, consultar precios o ayudarte a realizar un pedido."
            )

    if _is_drink_question(question):
        return _build_drink_response()

    multi_items = _extract_multi_pizza_items(question, pizza_names)
    if len(multi_items) > 1:
        return _build_multi_pizza_summary(multi_items, context)

    # FLUJO ACTIVO
    active_step = get_active_order_step(history, pizza_names)
    if active_step is not None:
        pizza = get_active_pizza(history, pizza_names) or "la pizza solicitada"
        if _detected_pizza_change(question, pizza_names, require_explicit=True):
            pizza_found = has_pizza_name(question, pizza_names)
            if pizza_found:
                return (
                    f"El cliente quiere cambiar a la Pizza {pizza_found}. "
                    f"REINICIA EL FLUJO y pregunta directamente por los extras disponibles."
                )
            else:
                return (
                    "El cliente quiere cambiar de pizza pero no especificó cuál. "
                    "Muestra el menú y pregunta: '¿A qué pizza te gustaría cambiar? 🍕'"
                )

        if active_step == 1:
            if is_pure_affirmation(question) and not is_no_in_order_flow(question):
                return (
                    f"El cliente quiere agregar extras pero no especificó cuál. "
                    f"Muéstrale las opciones de extras disponibles, CADA UNA CON SU PRECIO, "
                    f"usando EXCLUSIVAMENTE esta información (no inventes nada):\n\n"
                    f"{extras_context}\n\n"
                    f"REGLAS:\n"
                    f"1. Lista cada extra con su precio exacto tal como aparece arriba.\n"
                    f"2. Si un extra no tiene precio en el contexto, indica '(precio no disponible)'.\n"
                    f"3. Termina preguntando: '¿Cuál extra te gustaría agregar? ➕'"
                )

            # Parsear respuesta del cliente usando la MISMA lógica unificada
            parsed = parse_order_from_message(question, pizza_names, extras_context, context)
            
            # Si el cliente dijo "no" a extras, parsed.extras estará vacío
            if is_no_in_order_flow(question):
                parsed.extras = []
            
            # Verificar que tenemos el precio de la pizza
            if parsed.pizza_price is None:
                return LITERAL_RESPONSE_PREFIX + (
                    f"Tienes Pizza {pizza}. No pude confirmar el precio en este momento. "
                    f"¿Quieres que lo intente de nuevo o prefieres ver el menú?"
                )
            
            # Si hay items sin precio, NO avanzar a confirmación
            if not parsed.has_all_prices:
                missing = []
                for name, price in parsed.extras:
                    if price is None:
                        missing.append(name)
                for name, price in parsed.beverages:
                    if price is None:
                        missing.append(name)
                
                return LITERAL_RESPONSE_PREFIX + (
                    f"Identifiqué: Pizza {pizza}"
                    + (f" + Extras: {', '.join([n for n,_ in parsed.extras])}" if parsed.extras else "")
                    + (f" + Bebidas: {', '.join([n for n,_ in parsed.beverages])}" if parsed.beverages else "")
                    + f"\n\nPero no pude confirmar el precio de: {', '.join(missing)}. "
                    + f"¿Podrías confirmar qué {missing[0]} te refieres o si quieres ver la lista de extras/bebidas disponibles? ➕"
                )
            
            # TODO resuelto: armar pedido
            extras_display = "Ninguno"
            if parsed.extras:
                extras_display = ", ".join(name for name, _ in parsed.extras)
            
            if parsed.beverages:
                bev_names = ", ".join(name for name, _ in parsed.beverages)
                if extras_display == "Ninguno":
                    extras_display = bev_names
                else:
                    extras_display = f"{extras_display}, {bev_names}"
            
            observaciones = parsed.observations
            total = f"${parsed.total_price:.2f}"
            cantidad = _extract_quantity(history, pizza_names)
            total_con_cantidad = total
            if cantidad > 1 and total.startswith("$"):
                try:
                    precio_unitario = float(total.replace("$", ""))
                    total_con_cantidad = f"${precio_unitario * cantidad:.2f}"
                except ValueError:
                    pass
            
            return LITERAL_RESPONSE_PREFIX + (
                f"✅ ¡Perfecto! Tu pedido está listo:\n\n"
                f"📝 PEDIDO:\n"
                f"Cantidad: {cantidad}\n"
                f"Producto: Pizza {pizza}\n"
                f"Tamaño: Grande\n"
                f"Extras: {extras_display}\n"
                f"Observaciones: {observaciones}\n"
                f"Total: {total_con_cantidad}\n\n"
                f"¿Confirmas tu pedido? ✅"
            )

    # MENÚ
    if has_menu_intent(question):
        from services.menu_formatter import MenuFormatter
        menu_text = MenuFormatter().format()
        if menu_text:
            return LITERAL_RESPONSE_PREFIX + menu_text
        return (
            "Muestra el menú completo del CONTEXTO. "
            "Al final pregunta: '¿Cuál te llama la atención? 🍕'"
        )

    # NUEVA PIZZA -> Iniciar flujo (un solo paso: preguntar extras)
    # PERO si el mensaje ya incluye extras o bebida, armar pedido completo directamente
    pizza_found = has_pizza_name(question, pizza_names)
    if pizza_found:
        n_question = _normalize(question)
        if any(re.search(r'\b' + re.escape(kw) + r'\b', n_question) for kw in _QUESTION_NORM):
            return (
                f"El cliente preguntó sobre la Pizza {pizza_found}. "
                f"Responde SOLO con la información del CONTEXTO. "
                f"No inicies un flujo de pedido."
            )
        
        # Parsear el mensaje completo usando UNA SOLA FUENTE DE VERDAD
        # para extraer pizza, extras, bebidas y calcular total
        parsed = parse_order_from_message(question, pizza_names, extras_context, context)
        
        # Si no se pudo resolver la pizza, no avanzar
        if parsed.pizza_name is None:
            # Fallback al flujo normal
            pass
        elif parsed.pizza_price is None:
            # No se pudo encontrar precio de la pizza - avisar y no inventar
            return LITERAL_RESPONSE_PREFIX + (
                f"La Pizza {parsed.pizza_name} está en el menú, pero no pude consultar su precio en este momento. "
                f"¿Quieres que la busque de nuevo o prefieres ver el menú completo?"
            )
        elif not parsed.has_all_prices:
            # Faltan precios de algún extra/bebida - NO avanzar a confirmación
            # Preguntar al cliente para aclarar
            missing = []
            for name, price in parsed.extras:
                if price is None:
                    missing.append(name)
            for name, price in parsed.beverages:
                if price is None:
                    missing.append(name)
            
            return LITERAL_RESPONSE_PREFIX + (
                f"Identifiqué: Pizza {parsed.pizza_name}"
                + (f" + Extras: {', '.join([n for n,_ in parsed.extras])}" if parsed.extras else "")
                + (f" + Bebidas: {', '.join([n for n,_ in parsed.beverages])}" if parsed.beverages else "")
                + f"\n\nPero no pude confirmar el precio de: {', '.join(missing)}. "
                + f"¿Podrías confirmar qué {missing[0]} te refieres o si quieres ver la lista de extras/bebidas disponibles? ➕"
            )
        
        # TODO resuelto: todos los precios disponibles, armar pedido completo
        # Formatear extras para display
        extras_display = "Ninguno"
        if parsed.extras:
            extras_display = ", ".join(name for name, _ in parsed.extras)
        
        # Agregar bebidas a extras_display (las bebidas son parte del pedido)
        if parsed.beverages:
            bev_names = ", ".join(name for name, _ in parsed.beverages)
            if extras_display == "Ninguno":
                extras_display = bev_names
            else:
                extras_display = f"{extras_display}, {bev_names}"
        
        observaciones = parsed.observations
        total = f"${parsed.total_price:.2f}"
        cantidad = 1
        
        return LITERAL_RESPONSE_PREFIX + (
            f"✅ ¡Perfecto! Tu pedido está listo:\n\n"
            f"📝 PEDIDO:\n"
            f"Cantidad: {cantidad}\n"
            f"Producto: Pizza {parsed.pizza_name}\n"
            f"Tamaño: Grande\n"
            f"Extras: {extras_display}\n"
            f"Observaciones: {observaciones}\n"
            f"Total: {total}\n\n"
            f"¿Confirmas tu pedido? ✅"
        )
        
        # Si no hay extras/bebida en el mensaje, iniciar flujo normal
        extras_list = ""
        if extras_context:
            for line in extras_context.split("\n"):
                line = line.strip()
                if line.startswith("•") or line.startswith("-"):
                    extras_list += line + "\n"
        if extras_list:
            return LITERAL_RESPONSE_PREFIX + (
                f"¡Excelente elección! 🍕 La Pizza {pizza_found} está disponible.\n\n"
                f"Estos son los extras que puedes agregar:\n\n{extras_list}\n"
                f"¿Te gustaría agregar algún extra? ➕"
            )
        else:
            return LITERAL_RESPONSE_PREFIX + (
                f"¡Excelente elección! 🍕 La Pizza {pizza_found} está disponible.\n\n"
                f"¿Quieres confirmar tu pedido así? ✅"
            )

    if has_order_intent(question):
        return (
            "El cliente quiere ordenar pero no dijo qué pizza. "
            "Muestra el menú completo del CONTEXTO. "
            "Al final pregunta: '¿Cuál te llama la atención? 🍕'"
        )

    return LITERAL_RESPONSE_PREFIX + (
        "Puedo ayudarte con el menú, precios, ingredientes, extras o con un pedido de pizza."
    )
# ═══════════════════════════════════════════════════════════════════
# FLUJO V2 — CARRITO MULTI-ÍTEM CONTROLADO POR PYTHON
# Estas definiciones reemplazan las anteriores al cargarse al final.
# ═══════════════════════════════════════════════════════════════════

MAX_ORDER_QUANTITY = 20
_MATH_RE = re.compile(
    r"(?:\b(?:cuanto|cuánto)\s+es\b|\b(?:resuelve|calcula)\b).*?"
    r"(?:\d+\s*(?:\+|\-|\*|/|×|÷|\^|%)\s*\d+|raiz|raíz|integral|derivada|logaritmo)",
    re.IGNORECASE,
)
_CONFIRM_RE = re.compile(r"\b(?:si|sí|sip|confirmo|confirmas|confirma|confirmar|confirmar el pedido|correcto|adelante|procede|está bien|esta bien|es todo|eso es todo|si es todo|sí es todo|listo)\b", re.IGNORECASE)
_CHANGE_RE = re.compile(r"\b(?:mejor|cambia|cambiar|en vez de|reemplaza|no,?\s*mejor)\b", re.IGNORECASE)
_OBSERVATION_RE = re.compile(r"\b(?:observacion|observación|nota|que venga|entrega|caliente|bien cocida|bien cocido)\b", re.IGNORECASE)


def _is_skip_extras_answer(text: str) -> bool:
    """Detecta de forma cerrada respuestas que significan sin extras.

    No depende del historial ni del LLM y evita que respuestas cortas como
    "no" se pierdan por reglas más generales.
    """
    n = _normalize(text)
    return n in {
        "no", "ninguno", "ninguna", "nada", "sin extras",
        "asi esta bien", "esta bien", "no gracias", "sin nada",
    }


def is_math_question(text: str) -> bool:
    """Bloquea matemáticas ajenas al negocio; precios del menú se manejan aparte."""
    n = _normalize(text)
    if any(word in n for word in ("precio", "cuesta", "total", "pedido", "pizza", "extra")):
        return False
    return bool(_MATH_RE.search(text))


def _catalog_extras(extras_context: str) -> list[tuple[str, float]]:
    """Obtiene los extras de la misma fuente visible en ``ver menú``.

    Prioridad:
      1. Sección ``Extras`` generada por MenuFormatter (fuente de verdad).
      2. Contexto RAG de extras, únicamente como fallback.

    Nunca mezcla pizzas o bebidas dentro del catálogo de extras.
    """
    sources: list[str] = []
    try:
        from services.menu_formatter import MenuFormatter
        formatted = MenuFormatter().format()
        if formatted:
            # Recortar únicamente la sección Extras. Puede terminar antes de
            # promociones o de la pregunta final.
            match = re.search(
                r"(?is)➕\s*\*\*Extras(?:[^\n]*)\*\*\s*(.*?)(?=\n(?:🎉|¿Cuál)|\Z)",
                formatted,
            )
            if match:
                sources.append(match.group(1))
    except Exception:
        pass

    if extras_context:
        sources.append(extras_context)

    result: list[tuple[str, float]] = []
    seen: set[str] = set()
    for source in sources:
        for name, price in _parse_priced_items(source):
            clean = re.sub(r"\s+", " ", name).strip(" :-—")
            key = _normalize(clean)
            if not clean or key in seen:
                continue
            # Defensa adicional: solo nombres de extras, nunca pizzas/bebidas.
            if key.startswith("pizza ") or any(x in key for x in ("coca-cola", "bebida", "refresco")):
                continue
            seen.add(key)
            result.append((clean, price))
    return result


def _extras_menu_text(extras_context: str) -> str:
    extras = _catalog_extras(extras_context)
    if not extras:
        return "No hay extras registrados actualmente."
    return "\n".join(f"• {name} — ${price:.2f} MXN" for name, price in extras)


def _quantity_before_name(text: str, name: str) -> int:
    """Obtiene la cantidad escrita antes de una pizza válida.

    Acepta el nombre singular del catálogo y su forma plural natural:
    Margarita/Margaritas, Mexicana/Mexicanas, Pastorera/Pastoreras,
    Campirana/Campiranas y Pepperoni/Pepperonis.
    """
    n = _normalize(text)
    target = re.escape(_normalize(name))
    number_words = {
        "un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
        "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
        "nueve": 9, "diez": 10, "once": 11, "doce": 12,
        "trece": 13, "catorce": 14, "quince": 15, "dieciseis": 16,
        "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
        "veinte": 20,
    }
    words = "|".join(sorted(number_words, key=len, reverse=True))
    plural = rf"{target}(?:s|es)?"
    m = re.search(
        rf"(?:(\d+)|\b({words})\b)?\s*"
        rf"(?:pizzas?\s+)?(?:pizza\s+)?{plural}\b",
        n,
    )
    if not m:
        return 0
    if m.group(1):
        return int(m.group(1))
    if m.group(2):
        return number_words[m.group(2)]
    return 1


def _formatted_menu_catalog() -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Parsea la salida visible de ``ver menú`` como fuente única de precios.

    Devuelve (pizzas, extras, bebidas), indexados por nombre normalizado.
    """
    pizzas: dict[str, float] = {}
    extras: dict[str, float] = {}
    beverages: dict[str, float] = {}
    try:
        from services.menu_formatter import MenuFormatter
        menu = MenuFormatter().format() or ""
    except Exception:
        menu = ""

    section = ""
    for raw in menu.splitlines():
        line = raw.strip()
        nline = _normalize(line)
        if nline in {"pizzas", "**pizzas**"}:
            section = "pizzas"; continue
        if "bebidas" in nline and line.startswith(("🥤", "**")):
            section = "beverages"; continue
        if "extras" in nline and line.startswith(("➕", "**")):
            section = "extras"; continue
        if line.startswith("🎉") or line.startswith("¿"):
            section = ""
        if not line.startswith("•"):
            continue
        m = _PRICE_PATTERN.search(line)
        if not m:
            continue
        price = float(m.group(1).replace(",", "."))
        name = line[1:m.start()].strip(" •-—:*$")
        name = re.sub(r"\s*[—-]\s*$", "", name).strip()
        key = _normalize(name)
        if section == "pizzas":
            key = re.sub(r"^pizza\s+", "", key).strip()
            pizzas[key] = price
        elif section == "extras":
            extras[key] = price
        elif section == "beverages":
            beverages[key] = price
    return pizzas, extras, beverages


def _menu_pizza_price(name: str, context: str = "") -> float | None:
    pizzas, _, _ = _formatted_menu_catalog()
    key = re.sub(r"^pizza\s+", "", _normalize(name)).strip()
    if key in pizzas:
        return pizzas[key]
    return _extract_price_near(context, name)


def _beverage_catalog_item(context: str = "") -> dict | None:
    _, _, beverages = _formatted_menu_catalog()
    if beverages:
        key, price = next(iter(beverages.items()))
        # Nombre estable para la respuesta al cliente.
        return {"name": "Coca-Cola 1.35L", "price": price}
    return None


def _requested_beverage_quantity(text: str) -> int:
    n = _normalize(text)
    words = {"un":1,"una":1,"dos":2,"tres":3,"cuatro":4,"cinco":5,"seis":6,"siete":7,"ocho":8,"nueve":9,"diez":10}
    m = re.search(r"(?:(\d+)|\b(" + "|".join(words) + r")\b)?\s*(?:cocas?|coca-colas?|refrescos?|bebidas?)\b", n)
    if not m:
        return 0
    if m.group(1): return int(m.group(1))
    if m.group(2): return words[m.group(2)]
    return 1


def _extract_cart_items(text: str, pizza_names: list[str], context: str) -> tuple[list[dict], str | None]:
    """Extrae y EXPANDE cada pizza para poder asignar extras por unidad."""
    items: list[dict] = []
    total_qty = 0
    # La fuente determinista del menú siempre tiene prioridad sobre el
    # contexto RAG de la consulta. Esto evita precios cruzados o desactualizados
    # (por ejemplo Pastorera $240 desde un chunk cuando ``ver menú`` dice $220).
    menu_context = ""
    try:
        from services.rag_service import get_menu_context
        menu_context = get_menu_context() or ""
    except Exception:
        menu_context = ""
    if not menu_context:
        menu_context = context

    for name in sorted(pizza_names, key=len, reverse=True):
        qty = _quantity_before_name(text, name)
        if qty <= 0:
            continue
        total_qty += qty
        if total_qty > MAX_ORDER_QUANTITY:
            return [], f"Por el chat puedo registrar hasta {MAX_ORDER_QUANTITY} pizzas por pedido. Para una cantidad mayor se requiere una cotización especial."
        price = _menu_pizza_price(name, menu_context)
        if price is None:
            return [], f"No pude confirmar el precio de la Pizza {name}; no crearé el pedido hasta tener un precio válido."
        for unit in range(1, qty + 1):
            items.append({
                "pizza": name,
                "unit": unit,
                "base_price": price,
                "extras": [],
                "beverages": [],
                "observation": "",
            })
    return items, None


def _build_multi_order_directive(cart: dict, extras_context: str) -> str:
    """Directiva para que el LLM pregunte extras sin modificar productos ni precios."""
    items = cart.get("items", [])
    cursor = int(cart.get("cursor", 0))
    if not items or cursor >= len(items):
        return "El carrito no tiene un ítem pendiente."
    current = items[cursor]
    summary = ", ".join(f"Pizza {it['pizza']} #{it['unit']}" for it in items)
    return (
        f"El backend ya validó este carrito: {summary}. "
        f"Pregunta ÚNICAMENTE por extras para la Pizza {current['pizza']} "
        f"({cursor + 1} de {len(items)}). No cambies el producto, cantidad ni precios. "
        f"Muestra solo estos extras válidos:\n{_extras_menu_text(extras_context)}\n"
        f"Termina preguntando: '¿Qué extra deseas para esta pizza? Puedes responder ninguno. ➕'"
    )


def _find_requested_extras(text: str, extras_context: str) -> list[dict]:
    catalog = _catalog_extras(extras_context)
    n = _normalize(text)

    # En pedidos masivos, los extras suelen aparecer después de frases como
    # "agrégales", "ponles" o "a todas". Limitar la búsqueda a esa sección
    # evita interpretar "Pizza Pepperoni" como el extra pepperoni.
    scope = n
    marker = re.search(
        r"\b(?:agregales|agrégales|ponles|añadeles|añádeles|a todas|a las \d+)\b",
        n,
    )
    if marker:
        scope = n[marker.start():]
    else:
        # Caso normal: elimina nombres de pizza antes de buscar extras homónimos.
        scope = re.sub(r"\bpizzas?\s+pepperoni\b", " ", scope)

    if re.search(r"\b(?:con todo|todos los extras|todo)\b", scope):
        return [{"name": name, "price": price} for name, price in catalog]

    found: list[dict] = []
    seen: set[str] = set()
    for name, price in catalog:
        key = _normalize(name)
        if re.search(r"\b" + re.escape(key) + r"\b", scope) and key not in seen:
            seen.add(key)
            found.append({"name": name, "price": price})
    return found


def _find_requested_beverages(text: str, context: str) -> list[dict]:
    """Detecta bebida y cantidad usando el mismo catálogo que ``ver menú``."""
    qty = _requested_beverage_quantity(text)
    if qty <= 0:
        return []
    item = _beverage_catalog_item(context)
    if not item:
        return []
    return [{**item, "quantity": qty}]


def _unknown_extra_response(text: str, extras_context: str, context: str = "") -> str | None:
    if _is_skip_extras_answer(text) or is_no_in_order_flow(text) or is_pure_affirmation(text) or _OBSERVATION_RE.search(text):
        return None
    if _find_requested_extras(text, extras_context) or _find_requested_beverages(text, context):
        return None
    # Una respuesta libre durante extras no puede convertirse en producto.
    cleaned = re.sub(r"[^A-Za-zÁÉÍÓÚÑáéíóúñ0-9 ]", "", text).strip()
    if cleaned:
        return (
            f"'{cleaned}' no está registrado como extra. "
            "Solo puedo agregar productos existentes en el menú.\n\n"
            + _extras_menu_text(extras_context)
        )
    return None


def _apply_inline_selections_to_cart(
    question: str, cart: dict, extras_context: str, context: str
) -> tuple[bool, str | None]:
    """Aplica selecciones escritas en el mismo mensaje del pedido.

    Ejemplo soportado:
      "4 Margaritas, 4 Pepperoni... A las 20 agrégales queso extra y
       orilla de queso. Además quiero 20 Coca-Cola".

    Los extras indicados de forma global se copian a CADA pizza. Las bebidas
    se guardan a nivel del pedido para no multiplicarlas accidentalmente por
    el número de pizzas.
    """
    items = cart.get("items", [])
    if not items:
        return False, None

    extras = _find_requested_extras(question, extras_context)
    beverages = _find_requested_beverages(question, context)
    n = _normalize(question)

    mentions_extra = bool(
        extras
        or re.search(
            r"\b(?:extra|extras|agregales|agrégales|ponles|a todas|a las \d+)\b",
            n,
        )
    )
    mentions_beverage = bool(
        beverages
        or re.search(r"\b(?:coca(?:-cola)?|cocas?|refrescos?|bebidas?)\b", n)
    )

    if not mentions_extra and not mentions_beverage:
        return False, None

    if mentions_extra and not extras:
        return True, (
            "No encontré ese ingrediente en la lista de extras disponibles. "
            "No lo agregaré ni inventaré un precio.\n\n"
            + _extras_menu_text(extras_context)
            + "\n\nIndica uno de estos extras o responde ninguno."
        )

    # Copias independientes para que modificar una pizza después no altere
    # las demás por compartir la misma lista/diccionarios.
    for item in items:
        item["extras"] = [dict(extra) for extra in extras]
        item["beverages"] = []

    cart["beverages"] = [dict(beverage) for beverage in beverages]
    cart["cursor"] = len(items)
    cart["status"] = "awaiting_confirmation"
    return True, None


def _cart_total(cart: dict) -> float:
    total = 0.0
    for item in cart.get("items", []):
        total += float(item["base_price"])
        total += sum(float(e["price"]) for e in item.get("extras", []))
        total += sum(float(b["price"]) * int(b.get("quantity", 1)) for b in item.get("beverages", []))
    total += sum(float(b["price"]) * int(b.get("quantity", 1)) for b in cart.get("beverages", []))
    return total


def _cart_summary(cart: dict) -> str:
    """Construye un resumen compacto agrupando pizzas idénticas.

    Se consideran idénticas cuando coinciden:
    - tipo de pizza;
    - precio base;
    - extras;
    - bebidas individuales;
    - observación.

    Las bebidas generales del pedido se muestran una sola vez.
    """
    items = cart.get("items", [])

    grouped: dict[tuple, dict] = {}

    for item in items:
        extras = item.get("extras", [])
        beverages = item.get("beverages", [])

        extras_key = tuple(
            sorted(
                (
                    str(extra.get("name") or "").strip(),
                    float(extra.get("price") or 0),
                )
                for extra in extras
            )
        )
        beverages_key = tuple(
            sorted(
                (
                    str(beverage.get("name") or "").strip(),
                    float(beverage.get("price") or 0),
                    int(beverage.get("quantity", 1)),
                )
                for beverage in beverages
            )
        )

        key = (
            str(item.get("pizza") or "").strip(),
            float(item.get("base_price") or 0),
            extras_key,
            beverages_key,
            str(item.get("observation") or "").strip(),
        )

        if key not in grouped:
            grouped[key] = {
                "quantity": 0,
                "pizza": key[0],
                "base_price": key[1],
                "extras": extras,
                "beverages": beverages,
                "observation": key[4],
            }

        grouped[key]["quantity"] += 1

    lines = [
        "✅ ¡Perfecto! Tu pedido está listo:",
        "",
        "📝 PEDIDO:",
        f"Cantidad: {len(items)}",
        "Productos:",
    ]

    for group in grouped.values():
        quantity = int(group["quantity"])
        pizza_subtotal = quantity * float(group["base_price"])

        lines.append(
            f"• {quantity} × Pizza {group['pizza']} — ${pizza_subtotal:.2f}"
        )

        extras = group["extras"]
        if extras:
            lines.append(
                "  Extras por pizza: "
                + ", ".join(
                    f"{extra['name']} (${float(extra['price']):.2f})"
                    for extra in extras
                )
            )
        else:
            lines.append("  Extras: Ninguno")

        beverages = group["beverages"]
        if beverages:
            lines.append(
                "  Bebidas por pizza: "
                + ", ".join(
                    f"{int(beverage.get('quantity', 1))} × "
                    f"{beverage['name']} (${float(beverage['price']):.2f} c/u)"
                    for beverage in beverages
                )
            )

        if group["observation"]:
            lines.append(f"  Observaciones: {group['observation']}")

    order_beverages = cart.get("beverages", [])
    if order_beverages:
        lines.append("")
        lines.append(
            "Bebidas del pedido: "
            + ", ".join(
                f"{int(beverage.get('quantity', 1))} × "
                f"{beverage['name']} (${float(beverage['price']):.2f} c/u)"
                for beverage in order_beverages
            )
        )
    else:
        lines.append("")
        lines.append("Bebidas del pedido: Ninguna")

    lines.extend([
        "Tamaño: Grande",
        f"Total: ${_cart_total(cart):.2f} MXN",
        "",
        "¿Confirmas tu pedido? ✅",
    ])

    return "\n".join(lines)


def _first_item_extras_prompt(cart: dict, extras_context: str) -> str:
    """Inicia la selección individual después de que el cliente aceptó extras."""
    items = cart.get("items", [])
    if not items:
        return LITERAL_RESPONSE_PREFIX + "No hay pizzas activas en el carrito."
    first = items[0]
    return LITERAL_RESPONSE_PREFIX + (
        f"Perfecto. Revisaremos cada pizza por separado.\n\n"
        f"Pizza {first['pizza']} (1 de {len(items)}):\n\n"
        f"{_extras_menu_text(extras_context)}\n\n"
        "¿Qué extra deseas para esta pizza? Puedes responder ninguno. ➕"
    )


def _start_cart_response(cart: dict, extras_context: str) -> str:
    """Inicia el flujo sin obligar a recorrer todas las pizzas innecesariamente."""
    items = cart.get("items", [])
    if not items:
        return LITERAL_RESPONSE_PREFIX + "No hay pizzas activas en el carrito."

    base = [f"Registré {len(items)} pizza{'s' if len(items) != 1 else ''}:"]
    counts: dict[str, int] = {}
    for item in items:
        counts[item["pizza"]] = counts.get(item["pizza"], 0) + 1
    base.extend(f"• {qty} × Pizza {name}" for name, qty in counts.items())

    if len(items) > 1:
        cart["status"] = "asking_any_extras"
        base.extend([
            "",
            "¿Deseas agregar extras a alguna de las pizzas?",
            "Responde sí para configurarlas una por una, o no para continuar sin extras. ➕",
        ])
        return LITERAL_RESPONSE_PREFIX + "\n".join(base)

    cart["status"] = "collecting_extras"
    first = items[0]
    base.extend([
        "",
        f"Ahora configuraremos los extras de la Pizza {first['pizza']}.",
        "",
        _extras_menu_text(extras_context),
        "",
        "¿Qué extra deseas para esta pizza? Puedes responder ninguno. ➕",
    ])
    return LITERAL_RESPONSE_PREFIX + "\n".join(base)


def _reset_cart_for_change(question: str, pizza_names: list[str], context: str, current_cart: dict) -> tuple[str | None, dict | None]:
    if not _CHANGE_RE.search(question):
        return None, current_cart
    items, error = _extract_cart_items(question, pizza_names, context)
    if error:
        current_cart.clear()
        return LITERAL_RESPONSE_PREFIX + error, current_cart
    if not items:
        current_cart.clear()
        return LITERAL_RESPONSE_PREFIX + "Cancelé el carrito anterior. Indícame qué pizza válida deseas pedir.", current_cart
    owner = current_cart.get("user_id", 0)
    current_cart.clear()
    current_cart.update({"user_id": owner, "status": "collecting_extras", "cursor": 0, "items": items, "observations": []})
    return None, current_cart


def _is_informational_pizza_question(text: str, pizza_names: list[str]) -> bool:
    n = _normalize(text)
    return bool(has_pizza_name(text, pizza_names) and (
        "?" in text or re.search(r"\b(?:que tiene|qué tiene|ingredientes|incluye|contiene|como es|cómo es)\b", n)
    ))


def _resolve_referenced_pizza(
    question: str,
    history: list[dict],
    pizza_names: list[str],
) -> str | None:
    """Resuelve referencias como 'esa pizza', 'la quiero' o 'dame esa'."""
    explicit = has_pizza_name(question, pizza_names)
    if explicit:
        return explicit

    normalized = _normalize(question)
    has_reference = bool(re.search(
        r"\b(esa|esta|la misma|esa pizza|esta pizza|la quiero|me das esa|"
        r"quiero esa|dame esa|me puede dar esa|me puedes dar esa)\b",
        normalized,
    ))
    if not has_reference:
        return None

    for message in reversed(history[-8:]):
        content = str(message.get("content") or "")
        found = has_pizza_name(content, pizza_names)
        if found:
            return found

    return None


def _is_referenced_order_request(question: str) -> bool:
    """Detecta intención de ordenar una pizza mencionada previamente."""
    normalized = _normalize(question)
    has_order_verb = bool(re.search(
        r"\b(me das|dame|quiero|quisiera|me gustaria|me gustaría|"
        r"me puede dar|me puedes dar|ordenar|pedir)\b",
        normalized,
    ))
    has_reference = bool(re.search(
        r"\b(esa|esta|la misma|esa pizza|esta pizza|la quiero)\b",
        normalized,
    ))
    return has_order_verb and has_reference


def _extract_pizza_info_from_context(
    pizza_name: str,
    context: str,
) -> str | None:
    """Extrae de forma determinista la descripción de una pizza.

    Busca la sección correspondiente dentro del contexto del menú y evita
    utilizar historial, carrito o pedidos anteriores.
    """
    if not pizza_name or not context:
        return None

    clean_name = re.sub(r"^pizza\s+", "", pizza_name.strip(), flags=re.IGNORECASE)
    escaped = re.escape(clean_name)

    # Localizar el encabezado de la pizza.
    match = re.search(
        rf"(?:^|\n)\s*(?:🍕\s*)?(?:pizza\s+)?{escaped}\b",
        context,
        re.IGNORECASE,
    )
    if not match:
        return None

    section = context[match.start(): match.start() + 900]

    # Cortar cuando empieza otra pizza o una sección distinta.
    stop = re.search(
        r"\n\s*(?:🍕\s*)?(?:pizza\s+)"
        r"(?!"
        + escaped
        + r"\b)[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+"
        r"|\n\s*(?:bebidas|extras|promociones|horario)\b",
        section[1:],
        re.IGNORECASE,
    )
    if stop:
        section = section[: stop.start() + 1]

    lines = []
    for raw_line in section.splitlines():
        line = re.sub(r"^[\s•*\-–—]+", "", raw_line).strip()
        if not line:
            continue

        normalized = _normalize(line)

        # El encabezado y el precio se formatean por separado.
        if re.fullmatch(
            rf"(?:pizza\s+)?{escaped}",
            line,
            re.IGNORECASE,
        ):
            continue

        if re.search(r"\$\s*\d", line):
            continue

        # Conservar líneas descriptivas o de ingredientes.
        if (
            "ingrediente" in normalized
            or "lleva" in normalized
            or "contiene" in normalized
            or "incluye" in normalized
            or len(line.split(",")) >= 2
        ):
            lines.append(line)

    if not lines:
        return None

    # Deduplicar conservando orden.
    unique_lines = list(dict.fromkeys(lines))
    description = " ".join(unique_lines).strip()

    if not description:
        return None

    return f"🍕 La Pizza {clean_name} lleva: {description}"


def _is_general_help_question(text: str) -> bool:
    n = _normalize(text)
    return bool(re.search(r"\b(?:para que sirves|qué haces|que haces|como ayudas|cómo ayudas|ayuda)\b", n))


def _is_best_seller_question(text: str) -> bool:
    """Detecta consultas informativas sobre la pizza más popular.

    Estas frases no deben pasar por extract_unknown_pizza(), porque palabras
    como "más vendida" podrían interpretarse erróneamente como un nombre.
    """
    n = _normalize(text)
    return bool(
        re.search(
            r"\b(?:"
            r"cual|cuál|que|qué"
            r")\b.*\b(?:"
            r"mas vendida|más vendida|mas pedida|más pedida|"
            r"la favorita|favorita|mas popular|más popular|recomendada"
            r")\b",
            n,
        )
        or re.search(
            r"\b(?:pizza|producto)\s+(?:mas|más)\s+(?:vendida|pedido|pedida|popular)\b",
            n,
        )
    )


def _best_seller_response(best_seller: dict | None) -> str:
    if not best_seller:
        return (
            "No pude consultar la pizza más vendida en este momento. "
            "¿Quieres ver el menú completo?"
        )

    name = str(best_seller.get("nombre") or "").strip()
    price = str(best_seller.get("precio") or "").strip()
    ingredients = str(best_seller.get("ingredientes") or "").strip()

    if not name:
        return (
            "No pude consultar la pizza más vendida en este momento. "
            "¿Quieres ver el menú completo?"
        )

    display_name = name if _normalize(name).startswith("pizza ") else f"Pizza {name}"
    lines = [f"⭐ La pizza más vendida es la {display_name}."]

    if price and price.lower() != "consultar":
        lines.append(f"Precio: {price} MXN.")

    if ingredients and ingredients.lower() != "consultar en el menú":
        lines.append(f"Ingredientes: {ingredients}.")

    return "\n".join(lines)


def _modify_awaiting_cart(question: str, cart: dict, context: str) -> str | None:
    n = _normalize(question)
    if n in {"modificar", "modifica", "cambiar pedido", "quiero modificar"}:
        return "Indícame qué deseas modificar. Puedes agregar bebidas, cambiar la pizza o cancelar el pedido."
    qty = _requested_beverage_quantity(question)
    if qty and re.search(r"\b(?:agrega|agregar|añade|anade|pon|dame|quiero)\b", n):
        bev = _beverage_catalog_item(context)
        if not bev:
            return "No pude consultar la bebida disponible en este momento."
        cart["beverages"] = [{**bev, "quantity": qty}]
        return _cart_summary(cart)
    return None



def _recover_collecting_cart_from_history(
    history: list[dict],
    current_cart: dict | None,
    user_id: int = 0,
) -> dict | None:
    """Recupera un carrito de una pizza cuando la sesión perdió su estado.

    Se usa únicamente si el último mensaje del asistente pregunta por extras.
    Los precios se recuperan del menú determinista, nunca del texto libre.
    """
    if current_cart and current_cart.get("items"):
        return current_cart
    if not history:
        return current_cart

    last_assistant = str(history[-1].get("assistant") or "")
    normalized = _normalize(last_assistant)

    waiting_for_extras = (
        "que extra deseas para esta pizza" in normalized
        or "puedes responder ninguno" in normalized
        or "ahora configuraremos los extras de la pizza" in normalized
    )
    if not waiting_for_extras:
        return current_cart

    match = re.search(
        r"(?:1\s*[×x]\s*)?Pizza\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)",
        last_assistant,
        re.IGNORECASE,
    )
    if not match:
        return current_cart

    pizza_name = match.group(1).strip()
    pizza_catalog, _, _ = _formatted_menu_catalog()

    price = None
    for catalog_name, catalog_price in pizza_catalog.items():
        if _normalize(catalog_name) == _normalize(pizza_name):
            pizza_name = catalog_name
            price = float(catalog_price)
            break

    if price is None:
        return current_cart

    recovered = current_cart if isinstance(current_cart, dict) else {}

    # Guardar el propietario ANTES de limpiar el diccionario.
    previous_owner = recovered.get("user_id")
    owner_id = user_id or previous_owner or 0

    recovered.clear()
    recovered.update({
        "status": "collecting_extras",
        "items": [{
            "pizza": pizza_name,
            "base_price": price,
            "extras": [],
            "beverages": [],
            "observation": "",
        }],
        "cursor": 0,
        "beverages": [],
        "user_id": owner_id,
    })
    return recovered


def build_directive(
    question: str,
    pizza_names: list[str],
    history: list[dict],
    extras_context: str,
    context: str = "",
    promos_text: str = "",
    current_cart: dict | None = None,
    best_seller: dict | None = None,
    last_order: object | None = None,
    user_id: int = 0,
) -> str:
    """Controlador principal V2. El LLM nunca crea ni calcula un pedido."""
    cart = _recover_collecting_cart_from_history(
        history,
        current_cart,
        user_id=user_id,
    )
    n = _normalize(question)

    # Amenazas de privilegios y extracción de datos también son inyección.
    if re.search(r"\b(?:nivel admin|soy admin|administrador|datos registrados|datos de usuarios|base de datos|tablas|schema|credenciales)\b", n):
        return LITERAL_RESPONSE_PREFIX + "No puedo revelar datos internos, credenciales ni información de usuarios. Puedo ayudarte con el menú o un pedido."

    # 1. Seguridad y dominio.
    if is_math_question(question):
        return LITERAL_RESPONSE_PREFIX + "Solo puedo realizar cálculos relacionados con productos y precios del menú."
    if is_prompt_injection(question):
        return LITERAL_RESPONSE_PREFIX + "No puedo revelar información interna ni cambiar mi función. Puedo ayudarte con el menú, promociones vigentes o un pedido."

    # 2. Cancelación global.
    if has_cancel_intent(question):
        if cart is not None:
            cart.clear()
            cart.update({"status": "cancelled", "items": [], "cursor": 0, "user_id": cart.get("user_id", 0)})
        return LITERAL_RESPONSE_PREFIX + "✅ Pedido cancelado. ¿Quieres ver el menú? 🍕"

    # 3. Cambio de opinión tiene prioridad absoluta.
    if cart and cart.get("items") and _CHANGE_RE.search(question):
        response, cart = _reset_cart_for_change(question, pizza_names, context, cart)
        if response:
            return response
        return _start_cart_response(cart, extras_context)

    # 4. Confirmación del carrito: único paso posterior = pago.
    if cart and cart.get("status") == "awaiting_confirmation":
        modification = _modify_awaiting_cart(question, cart, context)
        if modification:
            return LITERAL_RESPONSE_PREFIX + modification
        if _CONFIRM_RE.search(question) or n in {
            "confirmar", "confirmado", "confirmalo", "confirmarlo",
            "si confirmo", "confirmo pedido", "confirmar pedido",
        }:
            cart["status"] = "awaiting_payment"
            return LITERAL_RESPONSE_PREFIX + (
                "✅ Pedido confirmado.\n\n💳 ¿Cómo deseas pagar?\n"
                "• Efectivo\n• Mercado Pago"
            )
        if has_order_intent(question) and not has_pizza_name(question, pizza_names):
            return LITERAL_RESPONSE_PREFIX + (
                "Ese producto no pertenece al menú y no modificaré tu pedido actual. "
                "Puedes confirmar, agregar Coca-Cola, cambiar la pizza o cancelar."
            )
        return LITERAL_RESPONSE_PREFIX + "Puedes confirmar el pedido, agregar bebidas, cambiar la pizza o cancelar."

    # 5. Pregunta previa para pedidos de varias pizzas.
    if cart and cart.get("status") == "asking_any_extras" and cart.get("items"):
        if _is_general_help_question(question):
            return LITERAL_RESPONSE_PREFIX + (
                "Tu pedido sigue guardado. Indica si deseas agregar extras a alguna pizza: sí o no."
            )

        if is_no_in_order_flow(question) or _is_skip_extras_answer(question):
            for item in cart["items"]:
                item["extras"] = []
                item["beverages"] = []
            cart["cursor"] = len(cart["items"])
            cart["status"] = "awaiting_confirmation"
            return LITERAL_RESPONSE_PREFIX + _cart_summary(cart)

        if is_pure_affirmation(question) or re.search(r"\b(?:si|sí|alguna|algunas)\b", n):
            cart["status"] = "collecting_extras"
            cart["cursor"] = 0
            return _first_item_extras_prompt(cart, extras_context)

        return LITERAL_RESPONSE_PREFIX + (
            "¿Deseas agregar extras a alguna de las pizzas? "
            "Responde sí para elegirlos o no para continuar sin extras."
        )

    # 5. Extras por unidad, usando el carrito aislado.
    if cart and cart.get("status") == "collecting_extras" and cart.get("items"):
        if _is_general_help_question(question):
            return LITERAL_RESPONSE_PREFIX + (
                "Puedo mostrarte el menú, explicar ingredientes, calcular precios del menú y gestionar tu pedido. "
                "Tu carrito sigue guardado; cuando quieras, indica un extra válido o responde ninguno."
            )
        cursor = int(cart.get("cursor", 0))
        if cursor >= len(cart["items"]):
            cart["status"] = "awaiting_confirmation"
            return LITERAL_RESPONSE_PREFIX + _cart_summary(cart)

        if is_pure_affirmation(question) and not is_no_in_order_flow(question):
            return LITERAL_RESPONSE_PREFIX + _extras_menu_text(extras_context) + "\n\n¿Cuál extra deseas agregar? ➕"

        unknown = _unknown_extra_response(question, extras_context, context)
        if unknown:
            return LITERAL_RESPONSE_PREFIX + unknown

        item = cart["items"][cursor]
        skip_extras = _is_skip_extras_answer(question) or is_no_in_order_flow(question)
        item["extras"] = [] if skip_extras else _find_requested_extras(question, extras_context)
        item["beverages"] = [] if skip_extras else _find_requested_beverages(question, context)
        if _OBSERVATION_RE.search(question):
            item["observation"] = question.strip()
        cart["cursor"] = cursor + 1

        if cart["cursor"] < len(cart["items"]):
            nxt = cart["items"][cart["cursor"]]
            return LITERAL_RESPONSE_PREFIX + (
                f"Extras guardados para la Pizza {item['pizza']} ({cursor + 1} de {len(cart['items'])}).\n\n"
                f"Ahora la Pizza {nxt['pizza']} ({cart['cursor'] + 1} de {len(cart['items'])}):\n\n"
                f"{_extras_menu_text(extras_context)}\n\n"
                "¿Qué extra deseas para esta pizza? Puedes responder ninguno. ➕"
            )

        cart["status"] = "awaiting_confirmation"
        return LITERAL_RESPONSE_PREFIX + _cart_summary(cart)

    # 6. Consulta informativa sobre la pizza más vendida.
    if _is_best_seller_question(question):
        return LITERAL_RESPONSE_PREFIX + _best_seller_response(best_seller)

    # 7. Menú completo, incluidas promociones informativas.
    if has_menu_intent(question):
        from services.menu_formatter import MenuFormatter
        return LITERAL_RESPONSE_PREFIX + (MenuFormatter().format() or "El menú no está disponible temporalmente.")

    # 7. Preguntas de precio, sin crear pedido.
    quote = _build_price_quote(question, pizza_names, context, extras_context)
    if quote:
        return quote

    # 7.5. Resolver pedidos por referencia contextual:
    # "me puede dar esa pizza", "quiero esa", "dame la misma".
    if _is_referenced_order_request(question):
        referenced_pizza = _resolve_referenced_pizza(
            question,
            history,
            pizza_names,
        )

        if referenced_pizza:
            menu_context = context
            try:
                from services.rag_service import get_menu_context
                menu_context = get_menu_context() or context
            except Exception:
                pass

            price = _menu_pizza_price(referenced_pizza, menu_context)
            if price is None:
                return LITERAL_RESPONSE_PREFIX + (
                    f"Encontré la Pizza {referenced_pizza}, pero no pude obtener "
                    "su precio del menú."
                )

            cart.clear()
            cart.update({
                "status": "collecting_extras",
                "items": [{
                    "pizza": referenced_pizza,
                    "base_price": price,
                    "extras": [],
                    "beverages": [],
                    "observation": "",
                }],
                "cursor": 0,
                "beverages": [],
                "user_id": user_id,
            })

            return LITERAL_RESPONSE_PREFIX + _first_item_extras_prompt(
                cart,
                extras_context,
            )

    # 8. Preguntas informativas sobre una pizza nunca crean carrito.
    if _is_informational_pizza_question(question, pizza_names):
        pizza = has_pizza_name(question, pizza_names)
        pizza_info = _extract_pizza_info_from_context(pizza, context)

        if pizza_info:
            return LITERAL_RESPONSE_PREFIX + pizza_info

        # Fallback controlado: no mostrar ni reconstruir pedidos anteriores.
        return LITERAL_RESPONSE_PREFIX + (
            f"No encontré la descripción de la Pizza {pizza} en el menú cargado. "
            "Puedo mostrarte el menú completo, pero no iniciaré un pedido."
        )

    # 9. Rechazar pizzas inexistentes antes de cualquier creación.
    unknown_pizza = extract_unknown_pizza(question, pizza_names)
    if unknown_pizza:
        return LITERAL_RESPONSE_PREFIX + f"La Pizza {unknown_pizza} no existe en nuestro menú. ¿Quieres ver las opciones disponibles?"
    if is_explicit_negated_order(question):
        return LITERAL_RESPONSE_PREFIX + "Entendido, no iniciaré ningún pedido."

    # 9. Crear carrito solo si aparecen pizzas válidas.
    items, error = _extract_cart_items(question, pizza_names, context)
    if error:
        return LITERAL_RESPONSE_PREFIX + error
    if items:
        if cart is None:
            # Compatibilidad sin sesión: se pregunta, pero no se finge persistencia.
            return LITERAL_RESPONSE_PREFIX + (
                "Identifiqué el pedido, pero la sesión no proporcionó un carrito aislado. "
                "Actualiza chat.py para pasar current_cart y evitar pérdida o mezcla de estado."
            )
        owner = cart.get("user_id", 0)
        cart.clear()
        cart.update({"user_id": owner, "status": "collecting_extras", "cursor": 0, "items": items, "observations": []})

        handled_inline, inline_error = _apply_inline_selections_to_cart(
            question, cart, extras_context, context
        )
        if handled_inline:
            if inline_error:
                return LITERAL_RESPONSE_PREFIX + inline_error
            return LITERAL_RESPONSE_PREFIX + _cart_summary(cart)

        return _start_cart_response(cart, extras_context)

    # 10. Pedido sin pizza: nunca dejar que el LLM invente una.
    if has_order_intent(question):
        return LITERAL_RESPONSE_PREFIX + "Para crear un pedido necesito que elijas una pizza válida del menú. ¿Quieres ver el menú completo? 🍕"

    # 11. Saludos personalizados.
    if is_only_greeting(question) or n in {"hols", "ola", "holaa", "holaaa"}:
        if last_order and getattr(last_order, "producto", ""):
            return LITERAL_RESPONSE_PREFIX + (
                f"¡Hola! 😊 Tu último pedido fue {last_order.producto}. "
                "¿Quieres repetirlo o prefieres ver el menú completo?"
            )
        if best_seller:
            nombre = best_seller.get("nombre", "la pizza más pedida")
            precio = best_seller.get("precio", "consultar")
            return LITERAL_RESPONSE_PREFIX + (
                f"¡Hola! 🍕 Bienvenido a Pizzería 220. Nuestra pizza más pedida es {nombre if _normalize(nombre).startswith('pizza ') else 'Pizza ' + nombre} ({precio} MXN). "
                "¿Te gustaría ver el menú completo?"
            )
        return LITERAL_RESPONSE_PREFIX + "¡Hola! 🍕 ¿Quieres ver el menú o hacer un pedido?"

    # 12. Promociones solo informativas salvo solicitud explícita.
    if any(k in n for k in ("promocion", "promoción", "promo", "oferta", "descuento")):
        if promos_text:
            return LITERAL_RESPONSE_PREFIX + "🎉 Promociones vigentes:\n" + promos_text
        return LITERAL_RESPONSE_PREFIX + "No hay promociones vigentes registradas en este momento."

    return LITERAL_RESPONSE_PREFIX + "Puedo ayudarte con el menú, promociones, precios o un pedido de pizza."