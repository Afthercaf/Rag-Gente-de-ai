"""
Detecta la intención del mensaje en Python antes de llamar al LLM.
La lógica de flujo vive aquí — el LLM solo genera texto.

──────────────────────────────────────────────────────────────────
FIX: Total del pedido (pizza + extras) calculado en Python
──────────────────────────────────────────────────────────────────
Antes, el directive final del pedido le pedía al LLM "calcula el
precio según el tamaño y los extras" (o simplemente no incluía un
Total). Eso es exactamente lo que produce precios inventados — por
algo existe _validate_extras_prices() en el servicio de respuesta,
como parche para detectar precios que no están en el CONTEXTO.

Ahora el Total se calcula aquí, en Python, ANTES de generar el
directive:

  Total = precio de la Pizza (buscado en `context`)
        + suma de los extras elegidos (buscados en `extras_context`)

Si no se puede determinar el precio de la pizza con certeza, o si el
cliente pidió un extra que no se pudo emparejar con ninguna línea de
`extras_context`, el Total se marca como "[precio no disponible]" en
vez de arriesgar un número incorrecto. El LLM solo COPIA el valor que
Python ya calculó — nunca se le pide que calcule nada.

Para que esto funcione, build_directive() ahora recibe un parámetro
extra `context` (el mismo texto de menú/RAG que ya se le pasa al LLM
en el prompt). Ver el cambio correspondiente en el servicio que llama
a build_directive(): hay que pasarle `context=context`.

⚠️ Nota sobre el parsing de precios: estoy asumiendo que tanto
`context` como `extras_context` marcan los precios con el símbolo
"$" (igual que asume _validate_extras_prices). Si tu CONTEXTO usa otro
formato (ej. "MXN 180", "180.00 pesos", sin símbolo $), dime el
formato exacto y ajusto _PRICE_PATTERN — con el formato real puedo
hacer esto bastante más confiable.
──────────────────────────────────────────────────────────────────
FIX: El Paso 2 (extras) se reseteaba a sí mismo y se repetía
──────────────────────────────────────────────────────────────────
Bug: al responder en el Paso 2 (decir el nombre de un extra, o decir
"no"), el sistema volvía a caer en el flujo de "información general"
en vez de avanzar al resumen final — daba la impresión de que el paso
de extras "se repetía" sin importar qué contestara el cliente.

Causa real: NO dependía de la respuesta del cliente. Dependía del
turno ANTERIOR, generado por el propio asistente. `_flow_terminated()`
buscaba palabras genéricas ("menú", "carta", "opciones") en cualquier
mensaje del asistente para decidir si el flujo ya había terminado.
Pero el directive del Paso 1 → Paso 2 le pide al LLM mostrar las
"opciones" de extras disponibles — es casi seguro que el LLM use esa
palabra al redactar su respuesta de forma natural. En cuanto lo hace,
`_flow_terminated()` lo detecta y `_get_flow_start()` resetea
`flow_start = None` justo en ese turno. Como no hay ningún turno
posterior que vuelva a fijar el inicio del flujo, `get_active_order_step()`
devuelve None desde ahí en adelante — sin importar qué responda el
cliente después (nombre de extra, "no", lo que sea), siempre cae al
fallback de "información general".

Fix: `_flow_terminated()` ya no usa esas palabras genéricas. Solo usa
las señales de FLOW_END_SIGNALS más la frase de cierre "¿Cuál te llama
la atención?", que es EXCLUSIVA de las respuestas que muestran el menú
completo (Casos 2, 4, y el rechazo de "repetir pedido") y nunca aparece
dentro del flujo de extras.
──────────────────────────────────────────────────────────────────
FIX: "Champiñones" (y similares) se confundían con un "no"
──────────────────────────────────────────────────────────────────
Bug: dentro del flujo de pedido, is_negative_or_skip() comparaba por
substring (`kw in n`), y uno de los keywords es "no" (2 letras). Eso
producía falso positivo con cualquier respuesta que contenga esas dos
letras juntas en otra palabra — ej. "champi-ñ-o-n-es" contiene "no". Si
el cliente respondía con ese nombre de extra, el sistema lo trataba
como si hubiera dicho "no quiero extras".

Fix: se agregó una función NUEVA y separada, is_no_in_order_flow(),
que usa un patrón regex con límites de palabra (\b) — así "no" solo
hace match cuando es una palabra completa, no una subcadena dentro de
otra palabra. Se usa SOLO dentro del flujo de pedido (Paso 1 y Paso 2,
más _compute_total), que es donde el cliente puede responder con el
nombre de un extra/ingrediente real. is_negative_or_skip() se deja
intacta con su comportamiento original (substring) para sus otros usos
(oferta de "repetir pedido", chequeo de intención de menú), donde ese
riesgo de colisión no aplica.
──────────────────────────────────────────────────────────────────
FIX: Flujo de pedido - "no" en Paso 1 debe avanzar a Paso 2 (extras)
──────────────────────────────────────────────────────────────────
Bug: Cuando el cliente decía "no" en el Paso 1 (ingredientes a quitar),
el sistema mostraba el menú completo de pizzas en lugar de avanzar
al Paso 2 (extras).

Causa: La directiva para el Paso 1 no especificaba explícitamente que
NO debía mostrar el menú completo. El LLM, al ver que el cliente
respondió "no", a veces interpretaba que quería ver el menú.

Fix: Se agregó una instrucción explícita en el Paso 1: "NO muestres el
menú completo de pizzas. Esto es sobre EXTRAS, no sobre pizzas."
Y se reforzó que debe preguntar: "¿Te gustaría agregar algún extra a
tu pizza? ➕"
──────────────────────────────────────────────────────────────────
FIX: Cambio de pizza - limpiar flujo anterior
──────────────────────────────────────────────────────────────────
Bug: Cuando el cliente decía "quiero cambiar a Pizza X", el sistema
mostraba el resumen del pedido ANTERIOR en lugar de iniciar un nuevo
flujo con la pizza seleccionada.

Causa: `_get_flow_start()` no detectaba que el usuario quería cambiar
de pizza, por lo que el flujo activo seguía apuntando a la pizza vieja.
Al generar el resumen final, usaba la pizza del flujo activo (la vieja)
en lugar de la nueva.

Fix: Se agregó detección de cambio de pizza en `_get_flow_start()`.
Cuando el usuario usa frases como "quiero cambiar a Pizza X", "otra
pizza", "cambiar pizza", etc., el flujo anterior se limpia y se inicia
uno nuevo con la pizza seleccionada.
──────────────────────────────────────────────────────────────────
FIX: El propio turno que inicia el pedido se autocancelaba
──────────────────────────────────────────────────────────────────
Bug: Después de que el cliente mencionaba una pizza por primera vez
("Pizza Campirana") y el asistente respondía "La Pizza X incluye:
[...]. ¿Deseas quitar alguno?", el flujo se "olvidaba" de sí mismo en
el turno SIGUIENTE: el cliente respondía "no" (Paso 1) y el sistema
mostraba el menú completo de pizzas en vez de avanzar a Paso 2
(extras) — y el mismo síntoma se repetía con cada "no" posterior,
como si el flujo de pedido no reaccionara a nada de lo que contestara
el cliente.

Causa: en `_get_flow_start()`, el check de "cambio de pizza" (antes
#4) se evaluaba ANTES que el check que fija `flow_start = i` (antes
#5), y usaba `continue`. `_detected_pizza_change()` con
`require_explicit=False` (el valor que usa este check) considera
"cambio de pizza" cualquier mensaje que mencione el nombre de una
pizza del catálogo — sin exigir un verbo de cambio — incluyendo el
mensaje que apenas está INICIANDO el pedido por primera vez. Resultado:
en el turno donde el asistente acababa de responder con el patrón
"...incluye: [...]. ¿Deseas quitar alguno?", el `continue` del check
de cambio de pizza saltaba el check que debía marcar ESE MISMO turno
como inicio del flujo. Como ningún turno posterior volvía a fijarlo,
`flow_start` quedaba en None para siempre — y por lo tanto
`get_active_order_step()` también, sin importar cuántas veces
respondiera el cliente.

Fix: se calcula `is_flow_start_turn` (el mismo patrón "incluye" +
"quitar") ANTES del check de cambio de pizza, y este último ahora se
omite si `is_flow_start_turn` es True. Si el asistente acaba de
responder con ese patrón — sea porque el cliente inició un pedido
nuevo o porque pidió cambiar de pizza a mitad de flujo — ese turno
SIEMPRE fija `flow_start = i`, sin que el check de cambio de pizza lo
pise.
──────────────────────────────────────────────────────────────────
"""

import re
import unicodedata
from typing import Optional, List, Tuple

# ══════════════════════════════════════════════════════════════════
# KEYWORDS
# ══════════════════════════════════════════════════════════════════

MENU_KEYWORDS = {
    "menu", "menú", "carta", "opciones", "qué tienen",
    "que tienen", "qué pizzas", "que pizzas", "ver menú",
    "ver menu", "qué hay", "que hay",
    "muestra", "enséñame", "enseñame", "mostrar", "ver",
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
    "no quiero", "no gracias", "mejor no", "cancelar", "cancela",
    "no me gusta", "no me agrada", "cambiar", "otra",
}

# Afirmaciones puras sin contenido — el cliente dice "sí quiero" pero no
# especifica QUÉ extra. No deben tomarse como el nombre del extra elegido;
# hay que volver a preguntar mostrando las opciones con precio.
PURE_AFFIRMATION_KEYWORDS = {
    "si", "sí", "claro", "va", "dale", "sale", "obvio",
    "por favor", "quiero extras", "si quiero", "sí quiero",
    "agregale", "agrégale", "ponle",
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

# Frase de cierre EXCLUSIVA de las respuestas que muestran el menú
# completo (Casos 2, 4, y el rechazo de "repetir pedido"). A diferencia
# de palabras genéricas como "menú"/"carta"/"opciones", esta frase nunca
# aparece dentro del flujo de extras, así que es segura para detectar
# "fin de flujo" sin riesgo de falso positivo. (Ver FIX en el docstring
# del módulo: las palabras genéricas se quitaron de aquí porque el LLM
# las usa de forma legítima al listar los extras disponibles.)
FLOW_END_EXCLUSIVE_PHRASE = "te llama la atención"

# Señal de que el asistente preguntó "¿lo mismo o ver el menú?" (CASO A)
# y está esperando la respuesta del cliente recurrente.
REPEAT_OFFER_SIGNAL = "ordenar lo mismo"

# Señal de que el asistente repreguntó "¿cuál extra?" porque el cliente
# afirmó sin especificar. Este turno no cuenta como respuesta final de
# extras — es una repregunta dentro del mismo paso.
WHICH_EXTRA_SIGNAL = "cuál extra te gustaría agregar"

# Patrón usado para encontrar precios marcados con "$" en cualquier
# bloque de texto (CONTEXTO general o extras_context). Mismo criterio
# que ya usa _validate_extras_prices() en el servicio de respuesta.
_PRICE_PATTERN = re.compile(r"\$\s*(\d+(?:[.,]\d{1,2})?)")

# ══════════════════════════════════════════════════════════════════
# RESPUESTA LITERAL — bypass total del LLM para el resumen final
# ══════════════════════════════════════════════════════════════════
# Prefijo que marca que el string devuelto por build_directive() NO es
# una instrucción para el LLM, sino el TEXTO FINAL que debe enviarse al
# cliente tal cual, sin pasar por el modelo. Se usa específicamente en
# el resumen final del pedido (fin del Paso 2): antes se le pedía al
# LLM "copia este texto literal, no recalcules nada", pero seguía
# siendo el LLM quien redactaba la respuesta — y nada garantiza que la
# copie bien (puede arrastrar un Producto/Total de un pedido anterior
# que aparece más arriba en el historial, por ejemplo). Con este
# prefijo, services/llm_service.py debe detectar el caso y devolver el
# texto directo, sin invocar al modelo — igual que el Total ya se
# calcula en Python en vez de pedírselo al LLM.
LITERAL_RESPONSE_PREFIX = "::LITERAL_RESPONSE::"

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
_PUREAFFIRM_NORM = _norm_set(PURE_AFFIRMATION_KEYWORDS)

# FIX: patrón con límites de palabra (\b) para NO_EXTRAS_KEYWORDS.
# Antes se usaba `kw in n` (substring), lo cual hacía match de "no"
# dentro de cualquier palabra que contuviera esas dos letras juntas
# (ej. "champiñones" → contiene "no"). Con \b, "no" solo hace match
# como palabra completa.
_NOEXT_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(k) for k in _NOEXT_NORM) + r")\b"
)


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


def _extract_order_quantity_from_text(text: str) -> int | None:
    """Extrae la cantidad de artículos desde un texto de pedido, si existe."""
    n = _normalize(text)
    match = re.search(r"\b(\d+)\s+(?:pizza|pizzas|bebida|bebidas|coca|coca-cola|cola)\b", n)
    if match:
        return int(match.group(1))

    match = re.search(r"\b(\d+)\s+\w+", n)
    if match:
        return int(match.group(1))
    return None


def _extract_beverage_from_text(text: str) -> str | None:
    """Extrae una bebida mencionada en el texto del pedido."""
    n = _normalize(text)
    beverage_keywords = {
        "coca cola": "Coca-Cola",
        "coca-cola": "Coca-Cola",
        "cola": "Coca-Cola",
        "sprite": "Sprite",
        "fanta": "Fanta",
        "aguas": "Agua",
        "agua": "Agua",
    }

    for keyword, value in beverage_keywords.items():
        if keyword in n:
            return value
    return None


def is_negative_or_skip(text: str) -> bool:
    """
    True si el usuario no quiere nada / confirma sin cambios.

    Uso GENERAL (substring, comportamiento original) — se usa fuera del
    flujo de personalización de pedido, ej. para distinguir "ver menú"
    de "no quiero ver el menú", o para la oferta de "repetir pedido".
    Ahí no hay riesgo real de que el cliente responda con el nombre de
    un extra/ingrediente, así que el substring simple es suficiente.

    DENTRO del flujo de pedido (Paso 1: ingredientes, Paso 2: extras) se
    usa en cambio is_no_in_order_flow() — ver esa función para el motivo.
    """
    n = _normalize(text)
    return any(kw in n for kw in _NOEXT_NORM)


def is_no_in_order_flow(text: str) -> bool:
    """
    True si, DENTRO del flujo de personalización del pedido (Paso 1:
    qué ingrediente quitar, Paso 2: qué extra agregar), el cliente está
    rechazando o saltando ese paso ("no", "ninguno", "así está bien",
    etc.).

    FIX: a diferencia de is_negative_or_skip() (substring), esta función
    usa un patrón con límites de palabra (\\b). El keyword "no" (2
    letras) por substring hacía falso positivo con cualquier nombre de
    extra/ingrediente que lo contenga como subcadena — ej. "Champiñones"
    contiene "no" — y el cliente terminaba "rechazando" algo que en
    realidad estaba pidiendo. Se usa SOLO en este contexto porque es
    justo donde el cliente puede responder con ese tipo de nombres;
    fuera del flujo de pedido is_negative_or_skip() sigue funcionando
    bien tal como estaba.
    """
    n = _normalize(text)
    return bool(_NOEXT_PATTERN.search(n))


def is_pure_affirmation(text: str) -> bool:
    """
    True si el usuario afirma que quiere extras ("sí", "claro", "dale")
    pero SIN mencionar cuál extra en concreto. Se usa para no confundir
    la palabra "sí" con el nombre de un extra al armar el resumen final;
    en ese caso hay que volver a preguntar cuál extra quiere, mostrando
    las opciones disponibles con su precio.
    """
    n = _normalize(text)
    words = set(re.findall(r"\w+", n))
    return bool(words & _PUREAFFIRM_NORM)


def _flow_terminated(assistant_msg: str) -> bool:
    """
    True si el mensaje del asistente indica que el flujo ya terminó.

    FIX: antes esta función también buscaba palabras genéricas como
    "menú", "carta", "opciones" en CUALQUIER mensaje del asistente.
    Eso rompía el flujo activo de forma silenciosa: el directive que
    pide mostrar los extras disponibles usa la palabra "opciones" al
    redactar la instrucción, y el LLM la repite de forma natural en su
    respuesta. En cuanto el asistente decía "opciones" al listar los
    extras, este chequeo lo interpretaba como "el asistente mostró el
    menú completo, el flujo terminó" y reseteaba flow_start = None —
    aunque en realidad seguía dentro del Paso 2. Como ningún turno
    posterior volvía a fijar el inicio del flujo, la respuesta del
    cliente (nombre de extra, "no", lo que fuera) siempre caía en el
    fallback de información general.

    Ahora solo se usan las señales explícitas de FLOW_END_SIGNALS más
    la frase de cierre "¿Cuál te llama la atención?", que es exclusiva
    de las respuestas de menú completo y nunca aparece dentro del flujo
    de personalización (ingredientes/extras).
    """
    n = _normalize(assistant_msg)
    signals = _FLOWEND_NORM | {_normalize(FLOW_END_EXCLUSIVE_PHRASE)}
    return any(signal in n for signal in signals)


def is_pending_repeat_offer(history: list[dict]) -> bool:
    """
    True si el ÚLTIMO turno del asistente fue la oferta de CASO A
    ("¿Te gustaría ordenar lo mismo o prefieres ver el menú completo?")
    y por lo tanto el sistema está esperando la respuesta del cliente
    a esa pregunta específica.

    Esto evita que un "no" en este punto caiga en el fallback genérico
    y el LLM termine inventando un resumen de pedido o un paso siguiente.
    """
    if not history:
        return False
    last_assistant = history[-1].get("assistant", "")
    return _normalize(REPEAT_OFFER_SIGNAL) in _normalize(last_assistant)


def has_previous_order(history: list[dict]) -> str | None:
    """Retorna el producto del último pedido confirmado, o None."""
    for msg in reversed(history):
        assistant_msg = msg.get("assistant", "")
        if "📝 PEDIDO:" in assistant_msg:
            for line in assistant_msg.split("\n"):
                if line.strip().startswith("Producto:"):
                    return line.split(":", 1)[1].strip()
    return None


def _detected_pizza_change(
    text: str,
    pizza_names: list[str] | None = None,
    require_explicit: bool = False,
) -> bool:
    """
    Detecta si el usuario quiere cambiar de pizza.

    Requiere evidencia real de que se trata de una PIZZA, no de cualquier
    cosa que el usuario rechace o pida. Dispara solo si:
      1. El texto usa un verbo de cambio inequívoco sin objeto ambiguo
         ("quiero cambiar", "cambiarla", "cambiármela").
      2. El texto menciona la palabra "pizza" explícitamente junto a un
         verbo de cambio/deseo ("quiero", "cambiar", "mejor", "otra").
      3. [SOLO SI require_explicit=False] El texto menciona un nombre
         real del catálogo (`pizza_names`), sin más contexto.

    El criterio 3 es deliberadamente más laxo y se omite cuando
    `require_explicit=True` — esto es necesario en el Paso 2 (esperando
    qué EXTRA quiere agregar), porque varios extras comparten nombre con
    pizzas del catálogo (ej. "pepperoni" es tanto un extra como una
    pizza). En ese contexto, una sola palabra como "pepperoni" debe
    interpretarse como el extra elegido, no como cambio de pizza, salvo
    que el cliente use un verbo de cambio explícito ("cambiar", "otra
    pizza", "mejor la pizza X").

    Sin el criterio 1/2 acotados a la palabra "pizza", frases como
    "no quiero extras" o "no quiero nada" se interpretaban erróneamente
    como "no quiero [la pizza] extras".
    """
    n = text.lower()

    # 1) Verbos de cambio inequívocos, sin necesidad de objeto.
    unambiguous_patterns = [
        r'quiero\s+cambiar',
        r'cambiarla',
        r'cambiármela',
    ]
    for pattern in unambiguous_patterns:
        if re.search(pattern, n):
            return True

    # 2) Patrones que EXIGEN la palabra "pizza" explícita junto al verbo,
    #    para no capturar objetos genéricos como "extras" o "nada".
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

    # 3) Mención directa de un nombre del catálogo real, SIN exigir
    #    verbo explícito. Solo aplica cuando NO se requiere evidencia
    #    explícita (ej. fuera del contexto de "¿qué extra quieres?").
    if not require_explicit and pizza_names and has_pizza_name(text, pizza_names):
        return True

    return False


def _get_pizza_names_from_history(history: list[dict]) -> list[str]:
    """
    Extrae nombres de pizza mencionados en el historial.
    Esto es un fallback para cuando no se pasan pizza_names.
    """
    names = set()
    for msg in history:
        for role in ("user", "assistant"):
            text = msg.get(role, "")
            # Buscar patrones como "Pizza [Nombre]"
            matches = re.findall(
                r'(?:pizza|🍕)\s+([A-ZÁ-Ú][a-záéíóúñ]+(?:\s+[A-ZÁ-Ú][a-záéíóúñ]+)*)',
                text,
                re.IGNORECASE
            )
            names.update(matches)
    return list(names)


# ══════════════════════════════════════════════════════════════════
# CÁLCULO DEL TOTAL (pizza + extras) — hecho en Python, no por el LLM
# ══════════════════════════════════════════════════════════════════

def _extract_price_near(text: str, target_name: str) -> float | None:
    """
    Busca `target_name` (sin tildes/mayúsculas) dentro de `text` y
    devuelve el primer precio "$NN" o "$NN.NN" que aparezca en esa
    misma línea, o en alguna de las 3 líneas siguientes si el nombre y
    el precio están en líneas separadas (ej. fichas tipo "Pizza X" /
    "Ingredientes: ..." / "Precio: $180").

    Devuelve None si no encuentra ninguna coincidencia clara — nunca
    inventa un número.
    """
    if not text or not target_name:
        return None

    target_norm = _normalize(target_name)
    lines = text.split("\n")

    for i, line in enumerate(lines):
        if target_norm in _normalize(line):
            match = _PRICE_PATTERN.search(line)
            if match:
                return float(match.group(1).replace(",", "."))
            for next_line in lines[i + 1: i + 4]:
                match = _PRICE_PATTERN.search(next_line)
                if match:
                    return float(match.group(1).replace(",", "."))
            break  # ya encontramos el bloque del nombre, no sigas buscando otro

    return None


def _parse_priced_items(block: str) -> list[tuple[str, float]]:
    """
    Parsea un bloque de extras tipo "• Nombre - $NN.NN" (uno por línea)
    en una lista de (nombre, precio). Tolera separadores -, :, espacios
    entre el nombre y el precio.
    """
    items: list[tuple[str, float]] = []
    if not block:
        return items

    pattern = re.compile(r"^[\s•\-\*]*([^$:\n]+?)\s*[:\-]?\s*\$\s*(\d+(?:[.,]\d{1,2})?)")
    for line in block.split("\n"):
        match = pattern.search(line)
        if match:
            name = match.group(1).strip()
            if name:
                items.append((name, float(match.group(2).replace(",", "."))))
    return items


def _sum_requested_extras(extra_answer: str, extras_context: str) -> tuple[float, list[str]]:
    """
    Revisa cada extra listado en `extras_context` y suma el precio de
    los que el cliente mencionó en `extra_answer` (texto libre, puede
    incluir más de uno, ej. "queso extra y pepperoni"). Devuelve
    (suma_total, nombres_encontrados). Si no hubo ningún match,
    devuelve (0.0, []) — eso se interpreta como "no se pudo resolver
    el precio del extra", no como "el extra es gratis".
    """
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


def _compute_total(pizza: str, extras_answer: str, extras_context: str, context: str) -> str:
    """
    Calcula el Total real del pedido:

        Total = precio de la Pizza (buscado en `context`)
              + suma de los extras elegidos (buscados en `extras_context`)

    Si el cliente no pidió extras ("Ninguno"), solo se cobra la pizza.
    Si pidió extras pero no se pudo emparejar ninguno con una línea de
    `extras_context` (ej. porque usó palabras distintas a las del
    catálogo), o si no se encontró el precio de la pizza, se devuelve
    "[precio no disponible]" en vez de arriesgar un número incorrecto.
    """
    pizza_price = _extract_price_near(context, pizza)

    if is_no_in_order_flow(extras_answer):
        extras_total, extras_resolved = 0.0, True
    else:
        extras_total, extras_found = _sum_requested_extras(extras_answer, extras_context)
        extras_resolved = bool(extras_found)

    if pizza_price is not None and extras_resolved:
        return f"${pizza_price + extras_total:.2f}"

    return "[precio no disponible]"


# ══════════════════════════════════════════════════════════════════
# DETECCIÓN DE FLUJO ACTIVO
# ══════════════════════════════════════════════════════════════════

def _get_flow_start(history: list[dict], pizza_names: list[str] | None = None) -> int | None:
    """
    Retorna el índice en `history` donde comenzó el flujo activo actual.
    Se limpia automáticamente si:
      - El usuario saluda de nuevo
      - El usuario pide el menú
      - El asistente emite una señal de finalización
      - 🔥 NUEVO: El usuario pide cambiar de pizza
    
    Args:
        history: Historial de conversación
        pizza_names: Lista de nombres de pizzas para detectar cambios
    """
    flow_start = None

    for i, msg in enumerate(history):
        user_msg = msg.get("user", "")
        assistant_msg = msg.get("assistant", "")

        # ── 1. Reinicio explícito si hay saludos ──────────────────────
        if is_only_greeting(user_msg):
            flow_start = None
            continue

        # ── 2. Reinicio por señales de fin de flujo ──────────────────
        if _flow_terminated(assistant_msg) or _flow_terminated(user_msg):
            flow_start = None
            continue
        
        # ── 3. Si el usuario pide menú, reiniciar ─────────────────────
        if has_menu_intent(user_msg) and not is_negative_or_skip(user_msg):
            flow_start = None
            continue

        # ── 4. ¿Este turno CONFIRMA una pizza (nueva o de cambio)? ────
        # Si el asistente respondió con "...incluye: [...]. ¿Deseas
        # quitar alguno?", este turno es, por definición, el inicio (o
        # reinicio) válido del flujo — sin importar si el cliente llegó
        # ahí mencionando una pizza por primera vez o pidiendo un cambio
        # a mitad de flujo. Se calcula ANTES del check de "cambio de
        # pizza" para que ese check no lo pise (ver FIX en el docstring
        # del módulo).
        is_flow_start_turn = (
            "incluye" in assistant_msg.lower() and "quitar" in assistant_msg.lower()
        )

        # ── 5. Si el usuario pide cambiar de pizza, reiniciar ─────────
        # FIX: antes este check se evaluaba SIEMPRE que el mensaje del
        # usuario mencionara el nombre de una pizza del catálogo (ese es
        # el criterio 3 de _detected_pizza_change, que no exige verbo de
        # cambio). Eso incluye el mensaje que recién está INICIANDO el
        # pedido (ej. "Pizza Campirana" la primera vez) — ese turno
        # disparaba este `continue` y saltaba el check de abajo (#6) que
        # debía fijar flow_start = i para ese mismo turno, dejando
        # flow_start en None para siempre. Ahora se omite si
        # is_flow_start_turn ya es True.
        if pizza_names and not is_flow_start_turn and _detected_pizza_change(user_msg, pizza_names):
            flow_start = None
            continue

        # ── 6. Inicio de nuevo flujo (Paso 1: pregunta de ingredientes) ──
        if is_flow_start_turn:
            flow_start = i

    return flow_start


def _filter_flow_replies(history: list[dict], flow_start: int) -> list[str]:
    """
    Retorna las respuestas reales del usuario al flujo de personalización
    iniciado en `flow_start`, EXCLUYENDO los turnos que forman parte de:

      a) Un desvío de CASO A (saludo -> oferta de repetir pedido ->
         respuesta del usuario a esa oferta). Esos turnos son una
         sub-conversación aparte y no cuentan como respuestas a
         "quitar ingredientes" / "agregar extras".

      b) Una repregunta de "¿cuál extra?" (el cliente dijo "sí" sin
         especificar cuál). El turno que DISPARÓ la repregunta (el "sí"
         ambiguo) no cuenta como respuesta final, pero el turno SIGUIENTE
         (donde el cliente ya nombra el extra concreto) sí cuenta — a
         diferencia del caso (a), aquí no se descarta la respuesta
         siguiente porque esa es justamente la respuesta real esperada.
    """
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
            # El turno actual (el "sí" ambiguo que disparó esta repregunta)
            # no cuenta. El siguiente turno (respuesta real) sí cuenta,
            # así que NO activamos skip_next aquí.
            continue

        replies.append(user_msg)

    return replies


def _get_user_reply_at(history: list[dict], offset: int) -> str:
    """
    Retorna el mensaje del usuario en la posición `offset`
    contando desde el inicio del flujo activo (0-indexed), excluyendo
    los turnos de desvío de CASO A.

      offset 0 → respuesta de ingredientes (qué quitar)
      offset 1 → respuesta de extras
    """
    flow_start = _get_flow_start(history)
    if flow_start is None:
        return ""

    replies = _filter_flow_replies(history, flow_start)
    return replies[offset] if offset < len(replies) else ""


def get_active_pizza(history: list[dict], pizza_names: list[str] | None = None) -> str | None:
    """
    Retorna el nombre de la pizza del flujo activo.

    PRIORIDAD 1: el turno de `flow_start` mismo. Ahí es donde el asistente
    confirma "La Pizza X incluye: [...]. ¿Deseas quitar alguno?" — esta es
    la fuente de verdad más confiable, porque el sistema ya determinó esa
    pizza como la activa para este flujo.

    PRIORIDAD 2 (fallback): el turno INMEDIATAMENTE ANTERIOR a flow_start,
    donde típicamente el usuario menciona el nombre al pedir. Solo se usa
    si la prioridad 1 no encuentra nada.

    ⚠️ Se busca turno por turno, no globalmente: si el turno anterior a
    flow_start fue, por ejemplo, un menú completo con varias pizzas
    listadas, NO debe usarse para esta búsqueda — el nombre correcto está
    en el turno de flow_start, y mezclar ambos turnos antes de filtrar
    hace que el primer nombre del catálogo que aparece en el menú (sin
    relación con el pedido real) gane por azar de orden en `pizza_names`.
    """
    flow_start = _get_flow_start(history, pizza_names)
    if flow_start is None:
        return None

    flow_start_msg = history[flow_start]
    previous_msg = history[flow_start - 1] if flow_start > 0 else None

    # 1) Buscar primero en el turno de flow_start (user, luego assistant).
    if pizza_names:
        for role in ("user", "assistant"):
            found = has_pizza_name(flow_start_msg.get(role, ""), pizza_names)
            if found:
                return found

    # 2) Fallback: turno anterior a flow_start (donde el usuario suele
    #    nombrar la pizza al pedirla por primera vez).
    if pizza_names and previous_msg:
        for role in ("user", "assistant"):
            found = has_pizza_name(previous_msg.get(role, ""), pizza_names)
            if found:
                return found

    # 3) Último recurso: regex genérico sobre flow_start y el turno anterior,
    #    buscando primero en "user", luego en "assistant".
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
    """
    Paso actual del flujo basado estrictamente en el número de respuestas
    que el usuario ha enviado desde que se inició la personalización.

    Los turnos que son parte de un DESVÍO de CASO A (el usuario saluda,
    el sistema ofrece repetir el pedido anterior, y el usuario responde
    a esa oferta) se EXCLUYEN del conteo: son una sub-conversación aparte
    y no respuestas reales a la pregunta de personalización activa
    (quitar ingredientes / agregar extras). Sin esta exclusión, un simple
    "hola" en medio del flujo corrompe el conteo de pasos y el flow_start
    original queda "fantasma" — contando turnos que ya no corresponden
    a la pregunta que realmente está pendiente.
    """
    flow_start = _get_flow_start(history, pizza_names)
    
    print(f"\n📊 [LOG TERMINAL] --- EVALUANDO PASO ACTIVO ---")
    print(f"🔍 [DEBUG] Índice flow_start detectado: {flow_start}")
    
    if flow_start is None:
        print("⚠️ [DEBUG] No hay un flujo activo iniciado.")
        return None

    # Filtramos y contamos cuántas respuestas reales ha dado el usuario DESDE flow_start,
    # excluyendo los turnos que forman parte de un desvío de CASO A.
    user_replies = _filter_flow_replies(history, flow_start)

    num_replies = len(user_replies)
    print(f"🔄 [DEBUG] Respuestas del usuario detectadas post-inicio: {num_replies} -> {user_replies}")

    # 0 respuestas en historial -> El usuario está respondiendo a los ingredientes base (Paso 1)
    # 1 respuesta en historial  -> El usuario ya respondió ingredientes, ahora responde a los extras (Paso 2)
    if num_replies == 0:
        print("🎯 [DEBUG] Match: Esperando respuesta de INGREDIENTES. -> PASO ACTIVO: 1")
        return 1
    elif num_replies == 1:
        print("🎯 [DEBUG] Match: Esperando respuesta de EXTRAS. -> PASO ACTIVO: 2")
        return 2

    print("🎯 [DEBUG] Flujo de personalización completado o excedido.")
    return None


# ══════════════════════════════════════════════════════════════════
# UTILIDAD PÚBLICA PARA EL SERVICIO QUE ENVUELVE A build_directive()
# ══════════════════════════════════════════════════════════════════

def is_order_flow_active(history: list[dict], pizza_names: list[str] | None = None) -> bool:
    """
    True si hay un flujo de pedido activo (Paso 1: ingredientes a
    quitar, o Paso 2: extras a agregar).

    ⚠️ ÚSALA EN TU SERVICIO PARA DECIDIR SI SE PUEDE USAR EL CACHÉ.

    Mientras el flujo está activo, la respuesta correcta a un mismo
    texto ("no", "sí", el nombre de un extra) depende 100% del PASO en
    el que está el cliente, no solo del texto en sí. Un caché que
    indexa por el texto crudo del mensaje (sin el estado de la
    conversación) puede devolver la respuesta de un "no" anterior — de
    OTRO punto del flujo — en vez de volver a evaluar el historial
    actual. Eso es exactamente lo que se observó: un "no" en Paso 1
    ("¿Deseas quitar alguno?") devolvió, desde caché, el menú completo
    que correspondía a un "no" anterior en un contexto distinto
    (rechazar la oferta de "repetir pedido"). build_directive() ni
    siquiera llegó a ejecutarse ese turno.

    Uso recomendado en el servicio, ANTES de consultar el caché:

        if is_order_flow_active(history):
            # No usar caché: la respuesta depende del paso actual,
            # no solo del texto del mensaje.
            directive = build_directive(question, pizza_names, history,
                                         extras_context, context=context)
        else:
            cached = cache.get(cache_key)
            if cached:
                print("📦 Respuesta desde caché")
                return cached
            directive = build_directive(question, pizza_names, history,
                                         extras_context, context=context)
            cache.set(cache_key, directive)
    """
    return get_active_order_step(history, pizza_names) is not None


# ══════════════════════════════════════════════════════════════════
# BUILD DIRECTIVE — punto de entrada principal
# ══════════════════════════════════════════════════════════════════

def build_directive(
    question: str,
    pizza_names: list[str],
    history: list[dict],
    extras_context: str,
    context: str = "",
) -> str:
    """
    Toda la lógica de decisión centralizada.
    """
    
    print(f"\n🚀 [LOG TERMINAL] --- NUEVA EVALUACIÓN DE DIRECTIVA ---")
    print(f"📥 Input Usuario (question): '{question}'")
    print(f"🗂️ Mensajes en Historial: {len(history)} turnos")
    
    # Mostrar los últimos 3 turnos para depuración
    print(f"📋 Últimos turnos:")
    for i, msg in enumerate(history[-5:]):
        print(f"  {i}: User: '{msg.get('user', '')[:30]}...' | Assistant: '{msg.get('assistant', '')[:30]}...'")

    # ── -1. RESPUESTA A OFERTA DE REPETIR PEDIDO (CASO A) ──────
    # CORRECCIÓN: Solo se activa si el ÚLTIMO mensaje del asistente
    # contiene "ordenar lo mismo" y el historial NO ha avanzado más allá
    # de esa oferta.
    if len(history) >= 1:
        last_assistant = history[-1].get("assistant", "")
        is_repeat_offer = _normalize(REPEAT_OFFER_SIGNAL) in _normalize(last_assistant)
        
        if is_repeat_offer:
            print("✅ [DEBUG MATCH] Caso detectado: RESPUESTA A OFERTA DE REPETIR PEDIDO")
            last_order = has_previous_order(history)
            
            # Verificar que el turno anterior (si existe) no sea un "no" que ya fue procesado
            # Si el usuario ya respondió "no" a la oferta, el asistente ya mostró el menú
            # y no deberíamos volver a entrar aquí.
            if len(history) >= 2:
                prev_user = history[-2].get("user", "").lower()
                if "no" in prev_user or "sí" in prev_user or "si" in prev_user:
                    # El usuario ya respondió a la oferta, el asistente ya mostró el menú
                    # No debemos volver a procesar esto.
                    print("⏭️ [DEBUG] El usuario ya respondió a la oferta. Saltando caso.")
                    pass
                else:
                    # Si el usuario NO ha respondido a la oferta, procesar normalmente
                    if is_negative_or_skip(question) and not has_pizza_name(question, pizza_names):
                        print("➡️ [DEBUG MATCH] Cliente rechazó repetir pedido -> mostrar menú")
                        return (
                            "El cliente NO quiere repetir su pedido anterior. "
                            "No generes ningún resumen de pedido ni preguntes por ubicación. "
                            "Muestra el menú completo del CONTEXTO. "
                            "Al final pregunta: '¿Cuál te llama la atención? 🍕'"
                        )
                    
                    pizza_found = has_pizza_name(question, pizza_names)
                    if pizza_found:
                        print(f"➡️ [DEBUG MATCH] Cliente eligió pizza distinta: {pizza_found}")
                        return (
                            f"El cliente quiere ordenar la Pizza {pizza_found} (tamaño Grande, único disponible). "
                            f"Consulta el CONTEXTO y dile qué ingredientes base incluye esa pizza. "
                            f"Luego pregunta si desea quitar alguno. "
                            f"Formato exacto: 'La Pizza {pizza_found} incluye: [ingredientes del CONTEXTO]. ¿Deseas quitar alguno? 🥗'"
                        )
                    
                    print(f"➡️ [DEBUG MATCH] Cliente quiere repetir: {last_order}")
                    nombre_pizza = last_order or "tu pizza anterior"
                    return (
                        f"El cliente quiere repetir su pedido anterior: {nombre_pizza} (tamaño Grande, único disponible). "
                        f"No vuelvas a preguntar si quiere lo mismo. "
                        f"Dile qué ingredientes base incluye esa pizza según el CONTEXTO y pregunta si desea quitar alguno. "
                        f"Formato exacto: '{nombre_pizza} incluye: [ingredientes del CONTEXTO]. ¿Deseas quitar alguno? 🥗'"
                    )

    # ── 0. SALUDO DE CLIENTE FRECUENTE (CASO A) ──────────────────
    last_order = has_previous_order(history)
    is_greeting_only = is_only_greeting(question)
    has_no_pizza = has_pizza_name(question, pizza_names) is None
    has_no_menu = not has_menu_intent(question)
    
    if is_greeting_only and has_no_pizza and has_no_menu:
        if last_order:
            print("✅ [DEBUG MATCH] Caso detectado: SALUDO CON HISTORIAL")
            return (
                f"El cliente saludó. Su último pedido fue: {last_order}. "
                f"Responde EXACTAMENTE con este texto, sin cambiar nada:\n"
                f"'¡Hola! 😊 La última vez pediste {last_order}. ¿Te gustaría ordenar lo mismo o prefieres ver el menú completo?'"
            )
        else:
            print("✅ [DEBUG MATCH] Caso detectado: SALUDO SIN HISTORIAL")
            return (
                "El cliente saludó. Es la primera vez que interactúa. "
                "Preséntate como el asistente de la pizzería y ofrece ayuda con el menú."
            )

    # ── 1. MENÚ EXPLÍCITO (prioridad alta) ───────────────────────
    if has_menu_intent(question) and not is_negative_or_skip(question):
        print("✅ [DEBUG MATCH] Caso detectado: MENÚ EXPLÍCITO (prioridad alta)")
        return LITERAL_RESPONSE_PREFIX + (
            "Entendido. 📋 Aquí tienes el menú completo. "
            "¿Cuál te llama la atención? 🍕"
        )

    # ── 2. FLUJO ACTIVO ──────────────────────────────────────────
    active_step = get_active_order_step(history, pizza_names)
    print(f"⚡ [DEBUG MATCH] Paso de flujo resuelto: {active_step}")

    if active_step is not None:
        pizza = get_active_pizza(history, pizza_names) or "la pizza solicitada"
        size = "Grande"

        # 🔥 NUEVO: Detectar cambio de pizza ANTES de procesar el paso activo
        # Esto asegura que un "quiero cambiar a Pizza X" tenga prioridad
        # sobre cualquier otra respuesta en el flujo actual
        require_explicit = (active_step == 2)  # En Paso 2, exigir verbo explícito
        if _detected_pizza_change(question, pizza_names, require_explicit=require_explicit):
            pizza_found = has_pizza_name(question, pizza_names)
            if pizza_found:
                print(f"🔄 [DEBUG] Cambio de pizza detectado en paso {active_step}: {pizza_found}")
                return (
                    f"El cliente quiere cambiar a la Pizza {pizza_found}. "
                    f"REINICIA EL FLUJO COMPLETAMENTE con esta nueva pizza. "
                    f"No uses la pizza anterior. "
                    f"Consulta el CONTEXTO y dile qué ingredientes base incluye la Pizza {pizza_found}. "
                    f"Luego pregunta si desea quitar alguno. "
                    f"Formato exacto: 'La Pizza {pizza_found} incluye: [ingredientes del CONTEXTO]. ¿Deseas quitar alguno? 🥗'"
                )
            else:
                return (
                    "El cliente quiere cambiar de pizza pero no especificó cuál. "
                    "Muestra el menú y pregunta: '¿A qué pizza te gustaría cambiar? 🍕'"
                )

        if active_step == 1:
            print("✅ [DEBUG MATCH] Ejecutando: FLUJO PASO 1")
            
            if is_no_in_order_flow(question):
                print("➡️ [DEBUG MATCH] Cliente NO quiere quitar ingredientes -> Avanzar a EXTRAS")
                
                if not extras_context:
                    return (
                        f"El cliente respondió '{question}' y no quiere quitar ingredientes. "
                        f"No hay información de extras disponibles. "
                        f"Responde EXACTAMENTE: '¡Entendido! 🍕 No tengo información sobre extras disponibles en este momento. "
                        f"¿Quieres confirmar tu pedido así? ✅'"
                    )
                
                if extras_context:
                    message = (
                        "¡Entendido! 🍕 Estos son los extras disponibles para tu pizza:\n"
                        f"{extras_context.strip()}\n"
                        "¿Te gustaría agregar alguno? ➕"
                    )
                else:
                    message = (
                        "¡Entendido! 🍕 No tengo información sobre extras disponibles en este momento."
                        "\n¿Quieres confirmar tu pedido así? ✅"
                    )
                return LITERAL_RESPONSE_PREFIX + message
            
            # El cliente SÍ quiere quitar algo — mostrar ingredientes
            return (
                f"El cliente respondió \"{question}\" a la pregunta de ingredientes de su Pizza {pizza} ({size}). "
                f"Confirma que se quitarán los ingredientes mencionados. "
                f"Luego, SI hay extras disponibles, pregunta si quiere agregar alguno."
            )

        if active_step == 2:
            print("✅ [DEBUG MATCH] Ejecutando: FLUJO PASO 2")
            
            if is_pure_affirmation(question) and not is_no_in_order_flow(question):
                print("➡️ [DEBUG MATCH] Afirmación pura sin extra específico -> repreguntar con opciones")
                return (
                    f"El cliente quiere agregar extras pero no especificó cuál. "
                    f"Muéstrale las opciones de extras disponibles, CADA UNA CON SU PRECIO, "
                    f"usando EXCLUSIVAMENTE esta información (no inventes nada):\n\n"
                    f"{extras_context}\n\n"
                    f"REGLAS:\n"
                    f"1. Lista cada extra con su precio exacto tal como aparece arriba.\n"
                    f"2. Si un extra no tiene precio en el contexto, indica '(precio no disponible)' junto a él, no inventes un monto.\n"
                    f"3. Termina preguntando: '¿Cuál extra te gustaría agregar? ➕'"
                )

            extras = "Ninguno" if is_no_in_order_flow(question) else question
            
            raw_removed = _get_user_reply_at(history, 0)
            removed_clean = "Ninguno" if (is_no_in_order_flow(raw_removed) or not raw_removed) else raw_removed

            total = _compute_total(pizza, question, extras_context, context)
            quantity = _extract_order_quantity_from_text(question) or 1
            beverage = _extract_beverage_from_text(question)
            beverage_line = f"Bebida: {beverage}\n" if beverage else ""

            # FIX: antes se le pedía al LLM que "copiara literal" este
            # resumen — pero seguía siendo el LLM quien lo redactaba, sin
            # garantía real de que respetara Producto/Total tal cual se
            # calcularon aquí (se observó un caso donde el resumen final
            # mostró la pizza y el total de un pedido anterior, ya
            # confirmado, en vez de la pizza recién elegida). Ahora se
            # devuelve el texto FINAL ya armado, con el prefijo
            # LITERAL_RESPONSE_PREFIX, para que llm_service.py lo
            # detecte y lo entregue directo al cliente sin pasar por el
            # modelo — el LLM ya no tiene oportunidad de alterar estos
            # valores.
            return LITERAL_RESPONSE_PREFIX + (
                f"✅ ¡Perfecto! Tu pedido está listo:\n\n"
                f"📝 PEDIDO:\n"
                f"Cantidad: {quantity}\n"
                f"Producto: Pizza {pizza}\n"
                f"Tamaño: {size}\n"
                f"Extras: {extras}\n"
                f"Ingredientes removidos: {removed_clean}\n"
                f"Total: {total}\n\n"
                f"¿Confirmas tu pedido? ✅"
            )

    # ── 3. MENÚ ──────────────────────────────────────────────────
    if has_menu_intent(question):
        print("✅ [DEBUG MATCH] Caso detectado: MENÚ COMPLETO")
        return (
            "Muestra el menú completo del CONTEXTO. "
            "No menciones pedidos anteriores ni pedidos en curso. "
            "Al final pregunta: '¿Cuál te llama la atención? 🍕'"
        )

    # ── 3. NUEVA PIZZA MENCIONADA ──────────────────────────────
    pizza_found = has_pizza_name(question, pizza_names)
    
    if pizza_found:
        is_question = any(kw in _normalize(question) for kw in _QUESTION_NORM)
        
        if is_question:
            print("✅ [DEBUG MATCH] Caso detectado: PREGUNTA SOBRE PIZZA")
            return (
                f"El cliente preguntó sobre la Pizza {pizza_found}. "
                f"Responde SOLO con la información disponible en el CONTEXTO. "
                f"No inicies un flujo de pedido. "
                f"No incluyas la sección 📝 PEDIDO."
            )
        
        print(f"✅ [DEBUG MATCH] Caso detectado: NUEVA PIZZA ENCONTRADA ({pizza_found}) -> Iniciar Flujo")
        return (
            f"El cliente quiere ordenar la Pizza {pizza_found} (tamaño Grande, único disponible). "
            f"Consulta el CONTEXTO y dile qué ingredientes base incluye esa pizza. "
            f"Luego pregunta si desea quitar alguno. "
            f"Formato exacto: 'La Pizza {pizza_found} incluye: [ingredientes del CONTEXTO]. ¿Deseas quitar alguno? 🥗'"
        )

    # ── 4. QUIERE ORDENAR SIN ESPECIFICAR PIZZA ─────────────────
    if has_order_intent(question):
        print("✅ [DEBUG MATCH] Caso detectado: INTENCIÓN DE ORDEN INDETERMINADA")
        return (
            "El cliente quiere ordenar pero no dijo qué pizza. "
            "Muestra el menú completo del CONTEXTO. "
            "Al final pregunta: '¿Cuál te llama la atención? 🍕'"
        )

    # ── 5. INFORMACIÓN GENERAL ──────────────────────────────────
    print("🚨 [DEBUG MATCH] Fallback: Caimos en INFORMACIÓN GENERAL (Default)")
    return (
        "Responde con la información disponible en el CONTEXTO. "
        "No incluyas la sección 📝 PEDIDO."
    )