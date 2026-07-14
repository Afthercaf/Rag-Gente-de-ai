import asyncio
import re
import logging
import os
import time
from typing import Optional, Dict, List, Set

from core.state import state
from utils.constants import TOP_K

logger = logging.getLogger(__name__)

# Cache en memoria
_pizza_names_cache: list[str] = []
_extras_cache: Dict[str, str] = {}  # cache por pizza_name

# ── Referencia estable de precios (para validación anti-alucinación) ──
_price_reference_cache: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# CONFIGURACIÓN - Para controlar el reranker
# ═══════════════════════════════════════════════════════════════════
# Si quieres desactivar el reranker para pruebas más rápidas:
USE_RERANKER = os.getenv("USE_RERANKER", "1").lower() in {"1", "true", "yes", "on"}


# ═══════════════════════════════════════════════════════════════════
# DEBUG: volcado a archivo de todo lo que trae el RAG
# ═══════════════════════════════════════════════════════════════════
_DEBUG_ENABLED = os.getenv("RAG_DEBUG_LOG", "1").lower() not in {"0", "false", "no"}
_DEBUG_LOG_PATH = os.getenv("RAG_DEBUG_LOG_PATH", "debug_rag_context.log")


def _debug_dump(label: str, query: str, content: str) -> None:
    """Guarda en disco (append) el contenido recuperado del RAG."""
    if not _DEBUG_ENABLED:
        return
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 70 + "\n")
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {label}\n")
            f.write(f"QUERY: {query!r}\n")
            f.write("-" * 70 + "\n")
            f.write(content if content else "(vacío)")
            f.write("\n")
    except Exception as e:
        logger.warning("No se pudo escribir el log de debug RAG: %s", e)


# ═══════════════════════════════════════════════════════════════════
# FILTRADO DE RUIDO - Elimina metadatos basura de los documentos RAG
# ═══════════════════════════════════════════════════════════════════

_NOISE_PATTERNS = [
    # Códigos/IDs internos
    r'\bcid:\s*\$\s*\d+',           # "cid: $127 MXN"
    r'\bclabe:\s*\$\s*\d+',         # "CLABE: $012910..."
    # Teléfonos formateados como precios
    r'\bwhatsapp:\s*\$\s*\d+',      # "WhatsApp: $9995466336 MXN"
    r'\btelefono:\s*\$\s*\d+',      # "Teléfono: $5512345678 MXN"
    r'\bcelular:\s*\$\s*\d+',       # "Celular: $5512345678 MXN"
    # Palabras que NO son productos con precio
    r'\bpizzer[ií]a:\s*\$\s*\d+',   # "Pizzería: $220 MXN"
    r'\bcalle:\s*\$\s*\d+',         # "calle: $47 MXN"
    r'\bn[uú]mero:\s*\$\s*\d+',     # "número: $123 MXN"
    r'\bdirecci[oó]n:\s*\$\s*\d+',  # "dirección: $123 MXN"
    r'\bcolonia:\s*\$\s*\d+',       # "colonia: $123 MXN"
    r'\bciudad:\s*\$\s*\d+',        # "ciudad: $123 MXN"
    r'\bestado:\s*\$\s*\d+',        # "estado: $123 MXN"
    r'\bc[oó]digo postal:\s*\$\s*\d+',  # "código postal: $123 MXN"
    r'\bcp:\s*\$\s*\d+',            # "CP: $123 MXN"
    r'\brfc:\s*\$\s*\d+',           # "RFC: $123 MXN"
    r'\bcurp:\s*\$\s*\d+',          # "CURP: $123 MXN"
    # Días de la semana como precios
    r'\blunes:\s*\$\s*\d+',         # "Lunes: $6 MXN"
    r'\bmartes:\s*\$\s*\d+',
    r'\bmi[eé]rcoles:\s*\$\s*\d+',
    r'\bjueves:\s*\$\s*\d+',
    r'\bviernes:\s*\$\s*\d+',
    r'\bs[aá]bado:\s*\$\s*\d+',
    r'\bdomingo:\s*\$\s*\d+',
    # Horarios
    r'\bhorario:\s*\$\s*\d+',
    r'\bapertura:\s*\$\s*\d+',
    r'\bcierre:\s*\$\s*\d+',
    # Frases genéricas
    r'\brespuestas? est[aá]n basadas en el men[uú]',  # "respuestas están basadas en el menú..."
    r'\bmen[uú] permanente de pizzer[ií]a',
    r'\b[úu]til para que el asistente',
    r'\binformaci[oó]n est[aá]tica para',
    r'\bingesta RAG',
    r'\bdocumento est[aá]tico',
    # Precios imposibles para pizzas (> $1000 o < $10)
    r'\$\s*(\d{4,})\s*MXN',         # $1000+ MXN
    r'\$\s*([1-9])\s*MXN',          # $1-9 MXN
]

_NOISE_REGEX = re.compile('|'.join(_NOISE_PATTERNS), re.IGNORECASE)

# Nombres válidos de pizzas para validar precios
_VALID_PIZZA_KEYWORDS = {
    'margarita', 'pepperoni', 'hawaiana', 'cuatro quesos', 'cuatroquesos',
    'vegetariana', 'barbacoa', 'carbonara', 'mexicana', 'napolitana',
    'prosciutto', 'funghi', 'diavola', 'capricciosa', 'tonno', 'parma',
    'campirana', 'pastorera', 'especial', 'deluxe', 'suprema', 'hawaiano',
}

def _filter_noise_lines(text: str) -> str:
    """
    Elimina líneas que contienen metadatos basura disfrazados de precios.
    Conserva solo líneas que parecen menú real (pizza + precio razonable).
    """
    if not text:
        return text
    
    lines = text.split('\n')
    clean_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # Si la línea NO tiene precio, mantenerla (puede ser contexto útil)
        if not re.search(r'\$\s*\d+', line_stripped):
            clean_lines.append(line)
            continue
        
        # La línea TIENE precio - verificar si es ruido
        if _NOISE_REGEX.search(line_stripped):
            continue  # Es ruido, descartar
        
        # Verificar si tiene palabras clave de pizza válidas
        has_pizza_keyword = any(kw in line_stripped.lower() for kw in _VALID_PIZZA_KEYWORDS)
        
        # También aceptar líneas con formato típico de menú: "• Nombre: $XXX"
        is_menu_format = bool(re.search(r'[•\-*]\s*[A-Za-zÁ-Úá-úñ]+\s*[:\-]?\s*\$\s*\d+', line_stripped))
        
        if has_pizza_keyword or is_menu_format:
            clean_lines.append(line)
        else:
            # Línea con precio pero sin palabras clave de pizza - posible ruido
            # Solo mantener si el precio está en rango razonable para pizza ($50-$500)
            price_match = re.search(r'\$\s*(\d+(?:[.,]\d{1,2})?)', line_stripped)
            if price_match:
                try:
                    price = float(price_match.group(1).replace(',', '.'))
                    if 50 <= price <= 500:
                        clean_lines.append(line)  # Precio razonable, mantener
                    # else: descartar precio fuera de rango
                except:
                    pass  # Si no se puede parsear, descartar
            # else: no hay precio parseable, descartar
    
    return '\n'.join(clean_lines)


# ═══════════════════════════════════════════════════════════════════
# RETRIEVE CONTEXT - VERSIÓN MEJORADA CON BÚSQUEDA HÍBRIDA + RERANKER
# ═══════════════════════════════════════════════════════════════════

# ── Reranker (lazy loading) ──────────────────────────────────────
_reranker = None
_reranker_loaded = False

def get_reranker():
    """Carga el modelo de reranker (lazy loading) solo si está habilitado."""
    global _reranker, _reranker_loaded
    
    # Si está desactivado, no cargar
    if not USE_RERANKER:
        print("⚠️ Reranker desactivado por configuración (USE_RERANKER=0)")
        return None
    
    if _reranker_loaded:
        return _reranker
    
    try:
        print("🔄 Cargando modelo de reranker BGE...")
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder('BAAI/bge-reranker-v2-m3')
        _reranker_loaded = True
        print("✅ Reranker cargado exitosamente")
        return _reranker
    except ImportError:
        print("⚠️ sentence-transformers no instalado. Reranker desactivado.")
        _reranker_loaded = True
        _reranker = None
        return None
    except Exception as e:
        print(f"⚠️ No se pudo cargar el reranker: {e}")
        _reranker_loaded = True
        _reranker = None
        return None


# ── Búsqueda híbrida (BM25 + Vectorial con RRF) ──────────────────
def _hybrid_search(query: str, docs_with_scores: list, k: int = 10) -> list:
    """
    Combina búsqueda vectorial y BM25 usando Reciprocal Rank Fusion (RRF).

    Args:
        query: Consulta del usuario.
        docs_with_scores: Lista de tuplas (Document, score_coseno) de ChromaDB.
        k: Número de documentos a retornar.
    """
    if not docs_with_scores:
        return []
    
    try:
        from rank_bm25 import BM25Okapi
        import numpy as np
        
        # Extraer solo los documentos (sin scores) para BM25
        docs = [item[0] for item in docs_with_scores]
        
        # 1. Preparar documentos para BM25 (tokenización)
        tokenized_docs = [doc.page_content.split() for doc in docs]
        bm25 = BM25Okapi(tokenized_docs)
        
        # 2. Obtener puntuaciones de BM25 para la consulta
        tokenized_query = query.split()
        bm25_scores = bm25.get_scores(tokenized_query)
        
        # 3. Reciprocal Rank Fusion (RRF)
        bm25_ranking = np.argsort(bm25_scores)[::-1]
        
        rrf_scores = {}
        for rank, idx in enumerate(bm25_ranking):
            rrf_scores[idx] = rrf_scores.get(idx, 0) + 1 / (rank + 60)
        
        # Componente vectorial: ordenar por score coseno REAL de ChromaDB
        # docs_with_scores ya viene ordenado por similitud descendente desde ChromaDB
        for rank, (doc, score) in enumerate(docs_with_scores):
            rrf_scores[rank] = rrf_scores.get(rank, 0) + 1 / (rank + 60)
        
        # Ordenar por puntuación RRF
        sorted_indices = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        
        return [docs[idx] for idx in sorted_indices[:k]]
        
    except ImportError:
        print("⚠️ rank_bm25 no instalado. Usando solo búsqueda vectorial.")
        return [item[0] for item in docs_with_scores[:k]]
    except Exception as e:
        print(f"⚠️ Error en búsqueda híbrida: {e}")
        return [item[0] for item in docs_with_scores[:k]]


# ── retrieve_context con búsqueda híbrida + reranker ─────────────
async def retrieve_context_with_rerank(search_query: str, top_k: int = 2) -> str:
    """
    Recupera contexto usando búsqueda híbrida + reranker (optimizado).
    """
    # 1. Usar un k más pequeño para pruebas
    k_initial = 5 if USE_RERANKER else 3  # Menos documentos = más rápido
    
    docs_with_scores = await asyncio.to_thread(
        state["db"].similarity_search_with_score,
        search_query,
        k=k_initial,
    )
    
    if not docs_with_scores:
        return ""
    
    # 2. Búsqueda híbrida (BM25 + Vectorial con scores reales) - si está instalado
    hybrid_docs = _hybrid_search(search_query, docs_with_scores, k=k_initial)
    
    # 3. Reranker - solo si está habilitado
    reranker = get_reranker()
    if reranker is not None:
        try:
            pairs = [[search_query, doc.page_content] for doc in hybrid_docs]
            scores = reranker.predict(pairs)
            
            ranked_docs = sorted(zip(hybrid_docs, scores), key=lambda x: x[1], reverse=True)
            final_docs = [doc for doc, score in ranked_docs[:top_k]]
            
            print(f"📊 [RERANKER] Seleccionados {len(final_docs)} de {len(hybrid_docs)} documentos")
            
        except Exception as e:
            print(f"⚠️ Error en reranker: {e}")
            final_docs = hybrid_docs[:top_k]
    else:
        final_docs = hybrid_docs[:top_k]
    
    result = "\n".join(doc.page_content for doc in final_docs)
    
    # 🔥 FILTRAR RUIDO DEL CONTEXTO (metadatos, teléfonos, códigos, etc.)
    result = _filter_noise_lines(result)
    
    _debug_dump("retrieve_context_with_rerank()", search_query, result)
    return result


# ── Función principal retrieve_context (VERSIÓN MEJORADA) ────────
async def retrieve_context(search_query: str) -> str:
    """
    Busca en ChromaDB con búsqueda híbrida (BM25 + vectorial) y reranker.
    Retorna el contexto como texto.
    """
    return await retrieve_context_with_rerank(search_query, top_k=3)


def get_promos_text() -> str:
    """Retorna el texto de todas las promociones cargadas."""
    return "\n".join(p.page_content for p in state["promo_documents"])


def build_full_context(rag_context: str, promos_text: str) -> str:
    return f"DOCUMENTOS:\n{rag_context}\n\nPROMOCIONES:\n{promos_text}"


def get_full_menu_price_reference() -> str:
    """
    Devuelve un contexto amplio y CACHEADO con todos los precios del menú.

    A diferencia de retrieve_context()/retrieve_context_with_rerank(), que
    usan top_k=2-3 y pueden variar de una consulta a otra, esta función
    trae un k más grande (20) y guarda el resultado en caché, así que no
    depende de qué chunk exacto haya recuperado el retrieval para una
    pregunta puntual del usuario.

    USO: exclusivamente como referencia para validar que el LLM no
    invente precios (_validate_extras_prices). NUNCA se debe mandar
    directamente al prompt del LLM como contexto de respuesta, porque
    no está filtrado/rankeado para relevancia — solo sirve para checar
    "¿este precio existe en algún lugar del menú real?".
    """
    global _price_reference_cache
    if _price_reference_cache is not None:
        return _price_reference_cache

    docs = state["db"].similarity_search("precio costo menú pizza MXN", k=20)
    _price_reference_cache = "\n".join(doc.page_content for doc in docs)
    # 🔥 FILTRAR RUIDO DE LA REFERENCIA DE PRECIOS
    _price_reference_cache = _filter_noise_lines(_price_reference_cache)
    return _price_reference_cache


# ═══════════════════════════════════════════════════════════════════
# EXTRACCIÓN DINÁMICA DE NOMBRES DE PIZZAS
# ═══════════════════════════════════════════════════════════════════

def _fetch_pizza_names_from_rag() -> list[str]:
    """Extrae nombres de pizzas del RAG usando patrones dinámicos."""
    try:
        docs = state["db"].similarity_search("pizza menu nombres", k=15)
        raw_text = "\n".join(doc.page_content for doc in docs)
        _debug_dump("_fetch_pizza_names_from_rag() - RAW", "pizza menu nombres", raw_text)

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
        _debug_dump("_fetch_pizza_names_from_rag() - RESULTADO", "pizza menu nombres", str(result))
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
    """Detecta secciones estructuradas en el texto sin usar keywords fijas."""
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
        
        title_match = re.match(
            r'^(?:(\d+\.\d+)\s+)?([A-ZÁ-Ú][a-záéíóúñ\s]+[.:]?)(?:\s+|$)',
            line
        )
        
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
            section_titles.append(current_section)
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
    """Extrae ítems (ingredientes, precios, etc.) de un texto."""
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
    """Extrae posibles ingredientes del texto sin usar keywords fijas."""
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
    """Separa el precio que viene pegado al último ingrediente en el texto del PDF."""
    price_pattern = re.compile(r'\$\s*(\d+(?:\.\d{2})?)\s*(?:MXN|mxn)?', re.IGNORECASE)
    common_price = ""
    clean_names: List[str] = []

    for item in items:
        m = price_pattern.search(item)
        if m:
            common_price = f"$ {m.group(1)} MXN"
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
    """Recupera información de extras y precios del menú del RAG (filtrado anti-ruido)."""
    global _extras_cache
    
    cache_key = f"extras_{pizza_name or 'general'}"
    if cache_key in _extras_cache:
        logger.debug(f"Usando caché para: {cache_key}")
        return _extras_cache[cache_key]
    
    try:
        if pizza_name:
            search_query = f"ingredientes adicionales extras {pizza_name}"
        else:
            search_query = "menu adicionales ingredientes extras precios pizzas"
        
        # Buscar con más documentos para capturar todo el menú
        docs = state["db"].similarity_search(search_query, k=15)
        full_text = "\n".join(doc.page_content for doc in docs)
        
        # 🔥 FILTRAR RUIDO ANTES DE PROCESAR
        full_text = _filter_noise_lines(full_text)
        _debug_dump("get_available_extras_context() - RAW", search_query, full_text)
        
        # ── EXTRAER PRECIOS DEL MENÚ (SOLO PIZZAS VÁLIDAS) ──────────
        menu_prices = []
        price_pattern = r'(?:Pizza\s+)?([A-ZÁ-Ú][a-záéíóúñ]+(?:\s+[A-ZÁ-Ú][a-záéíóúñ]+)*)\s*[:;]?\s*\$?\s*(\d+(?:[.,]\d{1,2})?)\s*(?:MXN|mxn|pesos)?'
        
        for match in re.finditer(price_pattern, full_text, re.IGNORECASE):
            name = match.group(1).strip()
            price = match.group(2).replace(",", ".")
            
            # Validar: nombre de pizza real + precio razonable
            if _is_valid_pizza_name(name) and _is_valid_price(price):
                menu_prices.append(f"  • {name}: ${price} MXN")
        
        # Deduplicar manteniendo orden
        seen = set()
        unique_prices = []
        for p in menu_prices:
            if p not in seen:
                seen.add(p)
                unique_prices.append(p)
        menu_prices = unique_prices[:20]  # Máx 20 pizzas
        
        # ── EXTRAER INGREDIENTES EXTRA ────────────────────────────
        structured = _detect_structured_sections(full_text)
        ingredients = _extract_ingredients_from_text(full_text)
        
        sections = []
        
        # 🔥 PRIMERO: Mostrar el menú con precios validados
        if menu_prices:
            sections.append("🍕 **Menú de Pizzería 220 (tamaño Grande):**")
            sections.extend(menu_prices)
            sections.append("")
        
        # Luego los extras
        if structured["elegibles"]:
            names, price = _clean_extras_and_extract_price(structured["elegibles"])
            price_label = f" ({price} c/u)" if price else ""
            sections.append(f"➕ **Ingredientes extra disponibles{price_label}:**")
            for item in names[:15]:
                price_suffix = f"  —  {price}" if price else ""
                sections.append(f"  • {item}{price_suffix}")
            sections.append("")
        
        if structured["no_elegibles"]:
            sections.append("❌ **Ingredientes que NO se pueden agregar:**")
            for item in structured["no_elegibles"][:10]:
                sections.append(f"  • {item}")
            sections.append("")
        
        # ── FALLBACK: si no se encontró nada estructurado ──────────
        if not sections:
            # Buscar líneas con precios
            price_lines = []
            for line in full_text.split('\n'):
                if re.search(r'\$\s*\d+', line):
                    price_lines.append(f"  • {line.strip()}")
            
            if price_lines:
                sections.append("📋 **Información del menú:**")
                sections.extend(price_lines[:20])
        
        result = "\n".join(sections) if sections else ""

        _extras_cache[cache_key] = result
        _debug_dump("get_available_extras_context() - RESULTADO", search_query, result)
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