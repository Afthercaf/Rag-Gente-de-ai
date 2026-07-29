import asyncio
import re
import logging
import unicodedata
from typing import Optional, Dict, List, Set

from core.state import state
from utils.constants import TOP_K

logger = logging.getLogger(__name__)

_UNTRUSTED_INSTRUCTION_RE = re.compile(
    r"\b(?:ignore|ignora|omite|olvida|system|developer|assistant|"
    r"prompt|instrucciones?|jailbreak|roleplay|act[uú]a como|"
    r"revela|muestra el contexto|ejecuta|tool call)\b",
    re.IGNORECASE,
)


def _sanitize_untrusted_context(value: str, *, max_chars: int = 20_000) -> str:
    """Convierte documentos externos en datos, descartando instrucciones."""
    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = re.sub(
        r"[\u200b-\u200f\u202a-\u202e\u2060\ufeff]",
        "",
        normalized,
    )
    safe_lines = []
    for line in normalized.splitlines():
        clean = line.strip()
        if not clean or _UNTRUSTED_INSTRUCTION_RE.search(clean):
            continue
        safe_lines.append(clean[:500])
    return "\n".join(safe_lines)[:max_chars]

# Cache en memoria
_pizza_names_cache: list[str] = []
_extras_cache: Dict[str, str] = {}  # cache por pizza_name
_menu_context_cache: Optional[str] = None  # cache del menú completo con precios
_best_seller_cache: Optional[Dict[str, str]] = None
_menu_lock = asyncio.Lock() if False else None  # simple, no async needed


# ═══════════════════════════════════════════════════════════════════
# RECUPERACIÓN ROBUSTA (BUG 4)
# Ninguna función de este módulo debe propagar una excepción de
# embeddings/RAG al endpoint /chat. Ante cualquier fallo devolvemos
# cadena vacía y registramos el error.
# ═══════════════════════════════════════════════════════════════════

async def retrieve_context(search_query: str) -> str:
    """Busca en el vector store y retorna el contexto como texto.

    ROBUSTO: si el vector store no está listo o falla la búsqueda
    (p.ej. el proveedor de embeddings local cae), captura la excepción, la registra y
    devuelve "" — NUNCA lanza. Así /chat nunca devuelve HTTP 500 por
    un fallo de embeddings.
    """
    try:
        db = state.get("db")
        if db is None:
            logger.warning("retrieve_context: vector store no disponible aún.")
            return ""
        docs = await asyncio.to_thread(db.similarity_search, search_query, k=TOP_K)
        return _sanitize_untrusted_context(
            "\n".join(doc.page_content for doc in docs)
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("retrieve_context falló (devolviendo ''): %s", exc, exc_info=True)
        return ""


def get_promos_text() -> str:
    """Retorna el texto de todas las promociones cargadas (robusto)."""
    try:
        return _sanitize_untrusted_context(
            "\n".join(
                p.page_content
                for p in state.get("promo_documents", []) or []
            )
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_promos_text falló: %s", exc)
        return ""


def build_full_context(rag_context: str, promos_text: str) -> str:
    """Construye el contexto interno para el prompt del LLM.

    IMPORTANTE: este contexto es SOLO para el modelo, NUNCA se muestra
    al usuario. Las etiquetas usadas son descriptivas para el modelo,
    no para el cliente.
    """
    parts = []
    if rag_context:
        safe_rag = _sanitize_untrusted_context(rag_context)
        if safe_rag:
            parts.append(f"<datos_rag>\n{safe_rag}\n</datos_rag>")
    if promos_text:
        safe_promos = _sanitize_untrusted_context(promos_text)
        if safe_promos:
            parts.append(f"<datos_promociones>\n{safe_promos}\n</datos_promociones>")
    return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════════════════
# CARGA DETERMINISTA DEL MENÚ (BUG 2)
# El menú NO se obtiene con una búsqueda semántica vaga ("menu pizza
# precios...") porque eso depende de que el índice ya esté poblado y
# del ranking del vector store — de ahí el "[precio no disponible]" en
# los primeros mensajes. En su lugar, escaneamos los documentos fuente
# (PDFs) una sola vez y extraemos TODOS los bloques de pizza/bebida con
# precio de forma determinista. Eso garantiza el menú completo con
# precios desde el primer mensaje.
# ═══════════════════════════════════════════════════════════════════

_PRICE_RE = re.compile(r"\$\s*(\d+(?:[.,]\d{1,2})?)")
_PIZZA_BLOCK_RE = re.compile(
    r"(pizza\s+[A-ZÁ-Ú][A-Za-záéíóúñ]+(?:\s+[A-ZÁ-Ú][A-Za-záéíóúñ]+)*)"
    r"(.*?)(?=\n\s*(?:pizza|bebida|🍕|•)\s|\Z)",
    re.IGNORECASE | re.DOTALL,
)
_BEVERAGE_RE = re.compile(
    r"(bebida|🥤)\s*[:\-]?\s*([^\n$]+(?:\$[^\n]+)?)", re.IGNORECASE
)


def _extract_menu_blocks_from_text(text: str) -> List[str]:
    """Extrae bloques de menú (pizzas + bebidas + extras con precio) de un texto."""
    blocks: List[str] = []
    seen: Set[str] = set()

    # 1) Líneas individuales "Nombre — $precio" o "Nombre: $precio"
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if _PRICE_RE.search(line) and re.search(
            r"pizza|bebida|refresco|cola|agua|jugo|🍕|🥤|extra|adicional|orilla", line, re.IGNORECASE
        ):
            key = line.lower()
            if key not in seen:
                seen.add(key)
                blocks.append(line)

    # 2) Bloques multilínea de pizza (nombre + ingredientes + precio)
    for m in _PIZZA_BLOCK_RE.finditer(text):
        name = m.group(1).strip()
        body = m.group(2).strip()
        if _PRICE_RE.search(body):
            block = f"{name}\n{body}".strip()
            key = block.lower()
            if key not in seen:
                seen.add(key)
                blocks.append(block)

    return blocks


def _load_menu_from_source_documents() -> List[str]:
    """Lee los PDFs fuente y extrae el menú completo (determinista)."""
    try:
        from src.file_processor import chunk_pdfs
        chunks = chunk_pdfs()
        full_text = "\n".join(c.page_content for c in chunks)
        blocks = _extract_menu_blocks_from_text(full_text)
        if blocks:
            return blocks
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo leer el menú desde PDFs: %s", exc)

    # Fallback: si no hay PDFs, intenta con búsqueda dirigida al vector store.
    try:
        db = state.get("db")
        if db is not None:
            docs = db.similarity_search(
                "menu pizzas precios bebidas ingredientes", k=20
            )
            blocks = []
            seen: Set[str] = set()
            for doc in docs:
                for b in _extract_menu_blocks_from_text(doc.page_content):
                    if b.lower() not in seen:
                        seen.add(b.lower())
                        blocks.append(b)
            if blocks:
                return blocks
    except Exception as exc:  # noqa: BLE001
        logger.warning("Fallback de menú por RAG falló: %s", exc)

    return []


def get_menu_context() -> str:
    """Retorna el menú completo con precios (cacheado y determinista).

    Esta es la MISMA fuente que usa el comando 'ver menú', de modo que
    bienvenida y 'ver menú' muestran precios idénticos. Se carga de forma
    determinista desde los documentos fuente (no de una búsqueda vaga),
    y se reintenta si la primera vez falla. Mientras no esté listo,
    devuelve "" y el llamador puede esperar a state['menu_loaded'].
    """
    global _menu_context_cache

    if _menu_context_cache is not None:
        return _menu_context_cache

    try:
        blocks = _load_menu_from_source_documents()
        if not blocks:
            logger.warning("get_menu_context: no se encontraron bloques de menú.")
            return ""
        _menu_context_cache = "\n".join(blocks)
        state["menu_loaded"] = True
        logger.info("🍕 Menú cacheado: %d bloques, %d caracteres",
                    len(blocks), len(_menu_context_cache))
        return _menu_context_cache
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error cacheando menú: %s", exc)
        return ""


def invalidate_menu_cache() -> None:
    """Invalida el cache del menú y fuerza recarga."""
    global _menu_context_cache
    _menu_context_cache = None
    state["menu_loaded"] = False


def format_menu_for_display() -> str:
    """Formatea el menú para mostrar al cliente (bienvenida / 'ver menú').

    Reutiliza get_menu_context() para garantizar precios idénticos.
    Usa MenuFormatter para generar un menú limpio y estructurado,
    SIN incluir chunks del RAG, FAQ, reglas del asistente ni ningún
    otro contenido interno.
    """
    from services.menu_formatter import MenuFormatter
    formatter = MenuFormatter()
    return formatter.format()


# ═══════════════════════════════════════════════════════════════════
# PRODUCTO MÁS VENDIDO (BUG 5)
# Se obtiene dinámicamente desde el historial de pedidos de Supabase;
# si no hay ventas registradas, usa un producto por defecto configurable
# vía .env (BEST_SELLER_DEFAULT). Nunca está codificado de forma fija.
# ═══════════════════════════════════════════════════════════════════

def get_best_seller() -> Dict[str, str]:
    """Devuelve {'nombre': ..., 'precio': ..., 'ingredientes': ...}.

    Prioridad:
      1. Estadísticas de ventas reales (campo 'pedido' de ordenes).
      2. Producto por defecto configurable (BEST_SELLER_DEFAULT en .env).
    Siempre cae a un valor por defecto razonable si todo falla.
    """
    global _best_seller_cache
    if _best_seller_cache is not None:
        return _best_seller_cache

    default_name = (os_getenv("BEST_SELLER_DEFAULT") or "Pizza Campirana").strip()

    # 1) Intentar estadísticas reales desde Supabase
    try:
        from collections import Counter
        from src.supabase_orders import _get_all_orders  # type: ignore
        orders = _get_all_orders()
        counts: Counter = Counter()
        for o in orders:
            pedido = (o.get("pedido") or "").lower()
            for name in get_pizza_names():
                if _normalize(name) in _normalize(pedido):
                    counts[name.title()] += 1
        if counts:
            top = counts.most_common(1)[0][0]
            result = _describe_product(top)
            _best_seller_cache = result
            return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudieron obtener estadísticas de ventas: %s", exc)

    # 2) Producto por defecto configurable
    result = _describe_product(default_name)
    _best_seller_cache = result
    return result


def _describe_product(name: str) -> Dict[str, str]:
    """Busca precio e ingredientes del producto en el menú cacheado."""
    menu = get_menu_context()
    nombre_norm = _normalize(name)
    precio = ""
    ingredientes = ""
    if menu:
        for block in menu.split("\n"):
            if nombre_norm in _normalize(block):
                m = _PRICE_RE.search(block)
                if m:
                    precio = f"${m.group(1)}"
                # intentar ingredientes en la misma línea tras 'incluye'
                ing = re.search(r"incluye[:\s]*(.+)", block, re.IGNORECASE)
                if ing:
                    ingredientes = ing.group(1).strip()
                break
    return {
        "nombre": name.title(),
        "precio": precio or "consultar",
        "ingredientes": ingredientes or "consultar en el menú",
    }


def invalidate_best_seller_cache() -> None:
    global _best_seller_cache
    _best_seller_cache = None


def _normalize(text: str) -> str:
    import unicodedata
    text = text.lower().strip()
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def os_getenv(key: str) -> str:
    import os
    return os.getenv(key, "")


# ═══════════════════════════════════════════════════════════════════
# NOMBRES DE PIZZAS (dinámicos, con fallback robusto)
# ═══════════════════════════════════════════════════════════════════

def _fetch_pizza_names_from_rag() -> list[str]:
    """Extrae nombres de pizzas del RAG usando patrones dinámicos."""
    try:
        db = state.get("db")
        if db is None:
            return []
        docs = db.similarity_search("pizza menu nombres", k=15)

        names: Set[str] = set()

        for doc in docs:
            text = doc.page_content

            pattern1 = re.findall(
                r'(?:^|\.\s*)(?:Pizza|🍕)\s+([A-ZÁ-Ú][a-záéíóúñ]+(?:\s+[A-ZÁ-Ú][a-záéíóúñ]+)*)',
                text,
                re.IGNORECASE
            )
            names.update(name.lower() for name in pattern1)

            pattern2 = re.findall(
                r'pizza\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)',
                text.lower()
            )
            names.update(pattern2)

            pattern3 = re.findall(
                r'(?:[•\-*]\s*)([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)(?=\s*[:$]|$)',
                text.lower()
            )
            stop_words = {'descripción', 'ingredientes', 'incluye', 'costo', 'precio',
                          'tamaño', 'grande', 'menú', 'pizza', 'queso', 'salsa'}
            for name in pattern3:
                if name not in stop_words and len(name) > 3:
                    if not any(stop in name for stop in ['descripción', 'ingredientes']):
                        names.add(name)

        cleaned = []
        for name in names:
            name = re.sub(r'(?:descripción|ingredientes|costo|precio).*$', '', name)
            name = name.strip()
            if name and len(name) > 2:
                cleaned.append(name)

        result = sorted(set(cleaned))
        logger.info("🍕 Pizzas cargadas del RAG: %s", result)
        return result

    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudieron cargar nombres de pizzas del RAG: %s", exc)
        return []


def get_pizza_names() -> list[str]:
    """Retorna únicamente pizzas confirmadas por la fuente determinista del menú."""
    global _pizza_names_cache
    if _pizza_names_cache:
        return _pizza_names_cache

    try:
        menu = get_menu_context()
        names: list[str] = []
        seen: Set[str] = set()
        for line in menu.splitlines():
            match = re.match(
                r"^\s*pizza\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]+)*)",
                line,
                re.IGNORECASE,
            )
            if not match:
                continue
            name = match.group(1).strip()
            key = _normalize(name)
            if key not in seen:
                seen.add(key)
                names.append(name)
        if names:
            _pizza_names_cache = names
            return _pizza_names_cache
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudieron extraer pizzas del menú determinista: %s", exc)

    # Fallback cerrado: usa solo los productos que el formateador reconoce,
    # nunca términos arbitrarios extraídos de chunks RAG.
    try:
        from services.menu_formatter import MenuFormatter
        _pizza_names_cache = sorted(name.title() for name in MenuFormatter.PIZZA_NAMES)
    except Exception:
        _pizza_names_cache = []
    return _pizza_names_cache


def invalidate_pizza_cache() -> None:
    global _pizza_names_cache
    _pizza_names_cache = []


def get_pizza_examples_for_prompt() -> str:
    """Genera ejemplos dinámicos usando nombres del RAG."""
    names = get_pizza_names()
    if not names:
        return ""

    verbs = ["quiero una", "dame una", "me das una", "quiero ordenar la"]
    examples = []

    for i, name in enumerate(names[:4]):
        verb = verbs[i % len(verbs)]
        examples.append(f'  - "{verb} {name.title()}"')

    return "\n".join(examples)


# ═══════════════════════════════════════════════════════════════════
# EXTRACCIÓN DINÁMICA DE EXTRAS - SIN KEYWORDS HARCODEADOS
# (robusta: nunca lanza)
# ═══════════════════════════════════════════════════════════════════

def _detect_structured_sections(text: str) -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {
        "elegibles": [], "no_elegibles": [], "adicionales": [], "precios": [], "otros": []
    }
    lines = text.split('\n')
    current_section = None
    section_buffer = []
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        title_match = re.match(r'^(?:(\d+\.\d+)\s+)?([A-ZÁ-Ú][a-záéíóúñ\s]+[.:]?)(?:\s+|$)', line)
        if title_match:
            if current_section and section_buffer:
                content = ' '.join(section_buffer)
                if 'elegible' in current_section.lower() or 'pueden' in current_section.lower():
                    result["elegibles"].extend(_extract_items_from_text(content))
                elif 'no elegible' in current_section.lower() or 'no pueden' in current_section.lower():
                    result["no_elegibles"].extend(_extract_items_from_text(content))
                elif 'adicional' in current_section.lower() or 'extra' in current_section.lower():
                    result["adicionales"].extend(_extract_items_from_text(content))
                else:
                    result["otros"].extend(_extract_items_from_text(content))
            current_section = title_match.group(2).strip()
            section_buffer = []
            continue
        if current_section:
            if re.match(r'^[\s]*[•\-*]\s+', line) or re.match(r'^[\s]*\d+\.\s+', line):
                clean = re.sub(r'^[\s]*[•\-*]\s+', '', line)
                clean = re.sub(r'^[\s]*\d+\.\s+', '', clean)
                section_buffer.append(clean)
            elif line and len(line) > 10:
                section_buffer.append(line)
    if current_section and section_buffer:
        content = ' '.join(section_buffer)
        if 'elegible' in current_section.lower() or 'pueden' in current_section.lower():
            result["elegibles"].extend(_extract_items_from_text(content))
        elif 'no elegible' in current_section.lower() or 'no pueden' in current_section.lower():
            result["no_elegibles"].extend(_extract_items_from_text(content))
        elif 'adicional' in current_section.lower() or 'extra' in current_section.lower():
            result["adicionales"].extend(_extract_items_from_text(content))
        else:
            result["otros"].extend(_extract_items_from_text(content))
    return result


def _extract_items_from_text(text: str) -> List[str]:
    items = []
    if ',' in text:
        parts = [p.strip() for p in text.split(',')]
        if len(parts) > 1:
            last = parts[-1]
            if ' y ' in last:
                parts[-1:] = [p.strip() for p in last.split(' y ')]
        items.extend(parts)
    elif ' y ' in text:
        items.extend([p.strip() for p in text.split(' y ')])
    elif '\n' in text:
        items.extend([p.strip() for p in text.split('\n') if p.strip()])
    else:
        items.append(text.strip())
    cleaned = []
    for item in items:
        if not item:
            continue
        item = re.sub(r'^[\d]+\.?\s*', '', item)
        item = re.sub(r'^[\s•\-*]+', '', item)
        item = re.sub(r'\s+', ' ', item).strip()
        if len(item) > 1 and not item.startswith(('la ', 'el ', 'los ', 'las ')):
            if re.search(r'\$\s*\d+', item):
                cleaned.append(item)
            elif len(item.split()) <= 4:
                cleaned.append(item)
    return list(dict.fromkeys(cleaned))


def _extract_ingredients_from_text(text: str) -> Set[str]:
    ingredients = set()
    list_patterns = [
        r'(?:ingredientes?|incluye|contiene|componentes?)\s*[:;]\s*([^.]+\n?)',
        r'(?:con|de)\s+([a-záéíóúñ]+(?:,\s*[a-záéíóúñ]+)*)',
    ]
    for pattern in list_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            parts = re.split(r',\s*|\s+y\s+|\s*&\s*', match)
            for part in parts:
                clean = part.strip().lower()
                if clean and len(clean) > 2:
                    ingredients.add(clean)
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        if re.search(r'\$\s*\d+', line):
            name_match = re.match(r'^([^$]+?)\s*\$', line)
            if name_match:
                name = name_match.group(1).strip()
                if name and len(name) > 2:
                    ingredients.add(name)
        if re.match(r'^[\s]*[•\-*]\s+', line):
            clean = re.sub(r'^[\s]*[•\-*]\s+', '', line)
            if clean and len(clean) > 2:
                ingredients.add(clean.lower())
    return ingredients


def _clean_extras_and_extract_price(items: List[str]) -> tuple[List[str], str]:
    price_pattern = re.compile(r'\$\s*(\d+(?:\.\d{2})?)\s*(?:MXN|mxn)?', re.IGNORECASE)
    common_price = ""
    clean_names: List[str] = []
    for item in items:
        m = price_pattern.search(item)
        if m:
            common_price = f"$ {m.group(1)} MXN"
            name = re.sub(r'\s*(?:cada\s+)?ingrediente[s]?\s+extra.*$', '', item, flags=re.IGNORECASE).strip()
            name = price_pattern.sub('', name).strip()
            if name and len(name) > 1:
                clean_names.append(name)
        else:
            clean_names.append(item)
    return clean_names, common_price


def get_available_extras_context(pizza_name: Optional[str] = None) -> str:
    """Recupera información de extras del RAG de forma 100% dinámica (robusta)."""
    global _extras_cache
    cache_key = f"extras_{pizza_name or 'general'}"
    if cache_key in _extras_cache:
        return _extras_cache[cache_key]
    try:
        db = state.get("db")
        if db is None:
            return ""
        if pizza_name:
            search_query = f"ingredientes adicionales extras {pizza_name}"
        else:
            search_query = "menu adicionales ingredientes extras"
        docs = db.similarity_search(search_query, k=TOP_K)
        full_text = "\n".join(doc.page_content for doc in docs)
        structured = _detect_structured_sections(full_text)
        ingredients = _extract_ingredients_from_text(full_text)
        if not any(structured.values()):
            blocks = re.split(r'\n{2,}', full_text)
            for block in blocks:
                if not block.strip():
                    continue
                if re.search(r'\$\s*\d+', block):
                    structured["adicionales"].extend(_extract_items_from_text(block))
                elif re.search(r'elegible|permitido|disponible', block, re.IGNORECASE):
                    structured["elegibles"].extend(_extract_items_from_text(block))
                elif re.search(r'no\s+elegible|no\s+permitido|no\s+disponible', block, re.IGNORECASE):
                    structured["no_elegibles"].extend(_extract_items_from_text(block))
        sections = []
        if structured["elegibles"]:
            names, price = _clean_extras_and_extract_price(structured["elegibles"])
            price_label = f" ({price} c/u)" if price else ""
            sections.append(f"🍕 **Ingredientes extra disponibles{price_label}:**")
            for item in names[:15]:
                price_suffix = f"  —  {price}" if price else ""
                sections.append(f"  • {item}{price_suffix}")
            sections.append("")
        if structured["no_elegibles"]:
            sections.append("❌ **Ingredientes que NO se pueden agregar:**")
            for item in structured["no_elegibles"][:10]:
                sections.append(f"  • {item}")
            sections.append("")
        _ADICIONALES_NOISE = {'menú', 'menu', 'pizza', 'ingrediente', 'ingredientes'}
        if structured["adicionales"]:
            real_adicionales = [it for it in structured["adicionales"]
                                if it.lower().strip() not in _ADICIONALES_NOISE and len(it.strip()) > 3]
            if real_adicionales:
                sections.append("💰 **Adicionales disponibles:**")
                for item in real_adicionales[:10]:
                    sections.append(f"  • {item}")
                sections.append("")
        if structured["precios"]:
            sections.append("💲 **Precios de adicionales:**")
            for item in structured["precios"][:10]:
                sections.append(f"  • {item}")
            sections.append("")
        if not sections and ingredients:
            sections.append("📋 **Ingredientes identificados:**")
            for item in sorted(list(ingredients))[:20]:
                sections.append(f"  • {item}")
            sections.append("")
        if not sections:
            relevant_lines = []
            for line in full_text.split('\n'):
                line = line.strip()
                if not line or len(line) < 5:
                    continue
                if re.search(r'[A-Za-záéíóúñ]+\s*\$\s*\d+', line):
                    relevant_lines.append(f"  • {line}")
                elif len(line.split()) <= 4 and len(line) > 3:
                    relevant_lines.append(f"  • {line}")
            if relevant_lines:
                sections.append("📋 **Información disponible:**")
                sections.extend(relevant_lines[:15])
        result = "\n".join(sections) if sections else ""
        _extras_cache[cache_key] = result
        return result
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error obteniendo extras desde RAG: %s", exc)
        return ""


def invalidate_extras_cache() -> None:
    global _extras_cache
    _extras_cache = {}


# ═══════════════════════════════════════════════════════════════════
# FUNCIONES DE COMPATIBILIDAD
# ═══════════════════════════════════════════════════════════════════

def get_available_sizes() -> list[str]:
    try:
        db = state.get("db")
        if db is None:
            return []
        docs = db.similarity_search("tamaño pizzas grande mediana personal", k=5)
        text = "\n".join(doc.page_content for doc in docs)
        sizes = re.findall(r'(personal|pequeña|mediana|grande|familiar|extra\s+grande)', text.lower())
        return list(set(s.capitalize() for s in sizes))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Error obteniendo tamaños: %s", exc)
        return []


def get_sizes_text() -> str:
    sizes = get_available_sizes()
    return ", ".join(sizes) if sizes else ""


def get_extras_text() -> str:
    return get_available_extras_context()


def get_extras_for_pizza(pizza_name: str) -> str:
    return get_available_extras_context(pizza_name)


def get_extras_prompt() -> str:
    context = get_available_extras_context()
    if not context:
        return "No se encontró información de extras en el menú."
    return f"Información de extras:\n\n{context}"
