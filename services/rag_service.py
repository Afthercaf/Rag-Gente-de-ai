import asyncio
import re
import logging
from typing import Optional, Dict, List, Set

from core.state import state
from utils.constants import TOP_K

logger = logging.getLogger(__name__)

# Cache en memoria
_pizza_names_cache: list[str] = []
_extras_cache: Dict[str, str] = {}  # cache por pizza_name


async def retrieve_context(search_query: str) -> str:
    """Busca en ChromaDB y retorna el contexto como texto."""
    docs = await asyncio.to_thread(
        state["db"].similarity_search,
        search_query,
        k=TOP_K,
    )
    return "\n".join(doc.page_content for doc in docs)


def get_promos_text() -> str:
    """Retorna el texto de todas las promociones cargadas."""
    return "\n".join(p.page_content for p in state["promo_documents"])


def build_full_context(rag_context: str, promos_text: str) -> str:
    return f"DOCUMENTOS:\n{rag_context}\n\nPROMOCIONES:\n{promos_text}"


# ═══════════════════════════════════════════════════════════════════
# EXTRACCIÓN DINÁMICA DE NOMBRES DE PIZZAS
# ═══════════════════════════════════════════════════════════════════

def _fetch_pizza_names_from_rag() -> list[str]:
    """Extrae nombres de pizzas del RAG usando patrones dinámicos."""
    try:
        docs = state["db"].similarity_search("pizza menu nombres", k=15)
        
        names: Set[str] = set()
        
        for doc in docs:
            text = doc.page_content
            
            # Patrón 1: "Pizza [Nombre]" al inicio de línea o después de punto
            pattern1 = re.findall(
                r'(?:^|\.\s*)(?:Pizza|🍕)\s+([A-ZÁ-Ú][a-záéíóúñ]+(?:\s+[A-ZÁ-Ú][a-záéíóúñ]+)*)',
                text,
                re.IGNORECASE
            )
            names.update(name.lower() for name in pattern1)
            
            # Patrón 2: "Pizza [Nombre]" en cualquier lugar
            pattern2 = re.findall(
                r'pizza\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)',
                text.lower()
            )
            names.update(pattern2)
            
            # Patrón 3: Nombres después de "•" o "-" en secciones de menú
            pattern3 = re.findall(
                r'(?:[•\-*]\s*)([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)(?=\s*[:$]|$)',
                text.lower()
            )
            # Filtrar palabras comunes que no son pizzas
            stop_words = {'descripción', 'ingredientes', 'incluye', 'costo', 'precio', 
                         'tamaño', 'grande', 'menú', 'pizza', 'queso', 'salsa'}
            for name in pattern3:
                if name not in stop_words and len(name) > 3:
                    # Verificar que no sea una frase genérica
                    if not any(stop in name for stop in ['descripción', 'ingredientes']):
                        names.add(name)
        
        # Limpiar nombres
        cleaned = []
        for name in names:
            # Eliminar descripciones pegadas
            name = re.sub(r'(?:descripción|ingredientes|costo|precio).*$', '', name)
            name = name.strip()
            if name and len(name) > 2:
                cleaned.append(name)
        
        # Eliminar duplicados y ordenar
        result = sorted(set(cleaned))
        logger.info("🍕 Pizzas cargadas del RAG: %s", result)
        return result

    except Exception as e:
        logger.warning("No se pudieron cargar nombres de pizzas del RAG: %s", e)
        return []


def get_pizza_names() -> list[str]:
    """Retorna los nombres de pizzas desde caché."""
    global _pizza_names_cache
    if not _pizza_names_cache:
        _pizza_names_cache = _fetch_pizza_names_from_rag()
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
# ═══════════════════════════════════════════════════════════════════

def _detect_structured_sections(text: str) -> Dict[str, List[str]]:
    """
    Detecta secciones estructuradas en el texto sin usar keywords fijas.
    Usa patrones de formato (números, títulos, viñetas) para identificar secciones.
    """
    result: Dict[str, List[str]] = {
        "elegibles": [],
        "no_elegibles": [],
        "adicionales": [],
        "precios": [],
        "otros": []
    }
    
    lines = text.split('\n')
    current_section = None
    section_buffer = []
    section_titles = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # Detectar títulos de sección por formato
        # Ej: "4.2 Ingredientes elegibles para el Menu"
        #     "4.3 Ingredientes no elegibles para el Menu"
        #     "4.4 Adicionales para el Menu"
        title_match = re.match(
            r'^(?:(\d+\.\d+)\s+)?([A-ZÁ-Ú][a-záéíóúñ\s]+[.:]?)(?:\s+|$)',
            line
        )
        
        if title_match:
            # Guardar sección anterior
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
            section_titles.append(current_section)
            continue
        
        # Si estamos dentro de una sección, acumular
        if current_section:
            # Si la línea parece un ítem de lista (con viñeta, guión, número)
            if re.match(r'^[\s]*[•\-*]\s+', line) or re.match(r'^[\s]*\d+\.\s+', line):
                # Limpiar y agregar
                clean = re.sub(r'^[\s]*[•\-*]\s+', '', line)
                clean = re.sub(r'^[\s]*\d+\.\s+', '', clean)
                section_buffer.append(clean)
            elif line and len(line) > 10:  # Texto descriptivo
                section_buffer.append(line)
    
    # Procesar última sección
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
    """
    Extrae ítems (ingredientes, precios, etc.) de un texto.
    Totalmente dinámico - no usa keywords fijos.
    """
    items = []
    
    # Intentar extraer por comas
    if ',' in text:
        parts = [p.strip() for p in text.split(',')]
        # Si hay "y" en la última parte, dividir también
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
    
    # Limpiar y filtrar
    cleaned = []
    for item in items:
        if not item:
            continue
        # Eliminar números de sección, prefijos, etc.
        item = re.sub(r'^[\d]+\.?\s*', '', item)
        item = re.sub(r'^[\s•\-*]+', '', item)
        item = re.sub(r'\s+', ' ', item).strip()
        # Eliminar palabras que suenan a descripciones generales
        if len(item) > 1 and not item.startswith(('la ', 'el ', 'los ', 'las ')):
            # Si tiene formato de precio, mantenerlo
            if re.search(r'\$\s*\d+', item):
                cleaned.append(item)
            elif len(item.split()) <= 4:  # Probablemente un ingrediente
                cleaned.append(item)
    
    return list(dict.fromkeys(cleaned))  # Eliminar duplicados manteniendo orden


def _extract_ingredients_from_text(text: str) -> Set[str]:
    """
    Extrae posibles ingredientes del texto sin usar keywords fijas.
    Busca patrones de listas y estructuras.
    """
    ingredients = set()
    
    # Buscar patrones de lista: "ingredientes: X, Y, Z" o "incluye X, Y, Z"
    list_patterns = [
        r'(?:ingredientes?|incluye|contiene|componentes?)\s*[:;]\s*([^.]+\n?)',
        r'(?:con|de)\s+([a-záéíóúñ]+(?:,\s*[a-záéíóúñ]+)*)',
    ]
    
    for pattern in list_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Dividir por comas, "y", "&"
            parts = re.split(r',\s*|\s+y\s+|\s*&\s*', match)
            for part in parts:
                clean = part.strip().lower()
                if clean and len(clean) > 2:
                    ingredients.add(clean)
    
    # Buscar líneas que parecen ítems de menú
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Si la línea tiene formato de precio, puede ser un adicional
        if re.search(r'\$\s*\d+', line):
            # Extraer el nombre del producto (antes del precio)
            name_match = re.match(r'^([^$]+?)\s*\$', line)
            if name_match:
                name = name_match.group(1).strip()
                if name and len(name) > 2:
                    ingredients.add(name)
        
        # Si la línea parece una lista con viñetas
        if re.match(r'^[\s]*[•\-*]\s+', line):
            clean = re.sub(r'^[\s]*[•\-*]\s+', '', line)
            if clean and len(clean) > 2:
                ingredients.add(clean.lower())
    
    return ingredients


def _clean_extras_and_extract_price(items: List[str]) -> tuple[List[str], str]:
    """
    Separa el precio que viene pegado al último ingrediente en el texto del PDF.
    
    El PDF suele tener el formato:
      "pepperoni, pimiento, cebolla, aceitunas, atún cada Ingrediente extra $ 45.00 MXN"
    
    Al splitear por comas, el último ítem queda como
      "atún cada Ingrediente extra $ 45.00 MXN"
    con el precio embebido. Esta función:
      1. Detecta el precio en cualquier ítem.
      2. Limpia el nombre del ítem (elimina el sufijo de precio).
      3. Devuelve (nombres_limpios, precio_formateado).
    El precio es "común" porque el PDF dice "cada ingrediente extra $ XX".
    """
    price_pattern = re.compile(r'\$\s*(\d+(?:\.\d{2})?)\s*(?:MXN|mxn)?', re.IGNORECASE)
    common_price = ""
    clean_names: List[str] = []

    for item in items:
        m = price_pattern.search(item)
        if m:
            # Guardar precio (formato normalizado)
            common_price = f"$ {m.group(1)} MXN"
            # Limpiar nombre: quitar texto que empieza en "cada" o directamente el precio
            name = re.sub(
                r'\s*(?:cada\s+)?ingrediente[s]?\s+extra.*$', '', item, flags=re.IGNORECASE
            ).strip()
            name = price_pattern.sub('', name).strip()
            if name and len(name) > 1:
                clean_names.append(name)
        else:
            clean_names.append(item)

    return clean_names, common_price


def get_available_extras_context(pizza_name: Optional[str] = None) -> str:
    """
    Recupera información de extras del RAG de forma 100% dinámica.
    """
    global _extras_cache
    
    cache_key = f"extras_{pizza_name or 'general'}"
    if cache_key in _extras_cache:
        logger.debug(f"Usando caché para: {cache_key}")
        return _extras_cache[cache_key]
    
    try:
        # Construir consulta dinámica
        if pizza_name:
            search_query = f"ingredientes adicionales extras {pizza_name}"
        else:
            search_query = "menu adicionales ingredientes extras"
        
        docs = state["db"].similarity_search(search_query, k=TOP_K)
        full_text = "\n".join(doc.page_content for doc in docs)
        
        # 1. Intentar extraer por secciones estructuradas
        structured = _detect_structured_sections(full_text)
        
        # 2. También extraer ingredientes directamente
        ingredients = _extract_ingredients_from_text(full_text)
        
        # 3. Si no hay secciones estructuradas, intentar con el texto completo
        if not any(structured.values()):
            # Dividir el texto en bloques temáticos
            blocks = re.split(r'\n{2,}', full_text)
            for block in blocks:
                if not block.strip():
                    continue
                # Si el bloque tiene precio, es un adicional
                if re.search(r'\$\s*\d+', block):
                    structured["adicionales"].extend(_extract_items_from_text(block))
                # Si el bloque habla de "elegible" o "permitido"
                elif re.search(r'elegible|permitido|disponible', block, re.IGNORECASE):
                    structured["elegibles"].extend(_extract_items_from_text(block))
                # Si habla de "no elegible" o "no permitido"
                elif re.search(r'no\s+elegible|no\s+permitido|no\s+disponible', block, re.IGNORECASE):
                    structured["no_elegibles"].extend(_extract_items_from_text(block))
        
        # Construir resultado
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
            real_adicionales = [
                it for it in structured["adicionales"]
                if it.lower().strip() not in _ADICIONALES_NOISE and len(it.strip()) > 3
            ]
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
        
        # Si no hay nada, usar ingredientes extraídos
        if not sections and ingredients:
            sections.append("📋 **Ingredientes identificados:**")
            for item in sorted(list(ingredients))[:20]:
                sections.append(f"  • {item}")
            sections.append("")
        
        # Si aún no hay nada, usar el texto filtrado
        if not sections:
            # Intentar extraer cualquier línea que parezca relevante
            relevant_lines = []
            for line in full_text.split('\n'):
                line = line.strip()
                if not line or len(line) < 5:
                    continue
                # Si la línea tiene formato de menú (nombre + precio)
                if re.search(r'[A-Za-záéíóúñ]+\s*\$\s*\d+', line):
                    relevant_lines.append(f"  • {line}")
                # Si la línea es corta (probablemente un nombre)
                elif len(line.split()) <= 4 and len(line) > 3:
                    relevant_lines.append(f"  • {line}")
            
            if relevant_lines:
                sections.append("📋 **Información disponible:**")
                sections.extend(relevant_lines[:15])
        
        result = "\n".join(sections) if sections else ""

        # Guardar en caché
        _extras_cache[cache_key] = result
        return result

    except Exception as e:
        logger.warning("Error obteniendo extras desde RAG: %s", e)
        return ""


def invalidate_extras_cache() -> None:
    global _extras_cache
    _extras_cache = {}


# ═══════════════════════════════════════════════════════════════════
# FUNCIONES DE COMPATIBILIDAD
# ═══════════════════════════════════════════════════════════════════

def get_available_sizes() -> list[str]:
    try:
        docs = state["db"].similarity_search("tamaño pizzas grande mediana personal", k=5)
        text = "\n".join(doc.page_content for doc in docs)
        
        # Buscar mención de tamaños
        sizes = re.findall(
            r'(personal|pequeña|mediana|grande|familiar|extra\s+grande)',
            text.lower()
        )
        
        return list(set(s.capitalize() for s in sizes))
    except Exception as e:
        logger.warning("Error obteniendo tamaños: %s", e)
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