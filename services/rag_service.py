import asyncio
import re
import logging

from core.state import state
from utils.constants import TOP_K

logger = logging.getLogger(__name__)

# Cache en memoria para no consultar el vectorstore en cada request
_pizza_names_cache: list[str] = []

# Valores por defecto para cuando el RAG no tiene información
_DEFAULT_SIZES = ["Pequeña", "Mediana", "Grande"]
_DEFAULT_EXTRAS = ["Queso extra", "Orilla de queso", "Pepperoni extra"]


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


def _fetch_pizza_names_from_rag() -> list[str]:
    """Consulta el vectorstore y extrae nombres de pizzas del contenido."""
    try:
        docs = state["db"].similarity_search("nombres de pizzas menú", k=10)

        names = []
        for doc in docs:
            # Captura "Pizza Mexicana", "Pizza BBQ", etc.
            found = re.findall(
                r"(?i)pizza\s+([A-ZÁ-Úa-záéíóú][a-záéíóú]+(?:\s+[A-ZÁ-Úa-záéíóú][a-záéíóú]+)*)",
                doc.page_content,
            )
            names.extend(found)

        unique = list({name.lower() for name in names})
        logger.info("🍕 Pizzas cargadas del RAG: %s", unique)
        return unique

    except Exception as e:
        logger.warning("No se pudieron cargar nombres de pizzas del RAG: %s", e)
        return []


def get_pizza_names() -> list[str]:
    """Retorna los nombres de pizzas desde caché o los carga del RAG."""
    global _pizza_names_cache
    if not _pizza_names_cache:
        _pizza_names_cache = _fetch_pizza_names_from_rag()
    return _pizza_names_cache


def invalidate_pizza_cache() -> None:
    """Invalida el caché. Úsala si actualizas el menú en el RAG."""
    global _pizza_names_cache
    _pizza_names_cache = []


def get_pizza_examples_for_prompt() -> str:
    """Genera ejemplos dinámicos de CASO C para el prompt usando nombres del RAG."""
    names = get_pizza_names()
    if not names:
        return ""

    # Verbos rotativos para que los ejemplos se vean naturales
    verbs = ["quiero una", "dame una", "me das una", "quiero ordenar la"]
    examples = []

    for i, name in enumerate(names[:4]):  # máximo 4 ejemplos
        verb = verbs[i % len(verbs)]
        examples.append(f'  - "{verb} {name.title()}"')

    return "\n".join(examples)


def get_available_sizes() -> list[str]:
    """
    Retorna los tamaños de pizza disponibles.
    Intenta extraer del RAG, si no, usa valores por defecto.
    """
    try:
        docs = state["db"].similarity_search("tamaños de pizza", k=5)
        sizes = set()
        
        size_patterns = [
            r"(personal|pequeña|mediana|grande|familiar|extra\s+grande)",
            r"(chica|mediana|grande|familiar)",
        ]
        
        for doc in docs:
            content_lower = doc.page_content.lower()
            for pattern in size_patterns:
                matches = re.findall(pattern, content_lower)
                sizes.update(matches)
        
        if sizes:
            # Limpiar y capitalizar
            clean_sizes = [s.capitalize() for s in sizes]
            logger.info(f"📏 Tamaños encontrados en RAG: {clean_sizes}")
            return clean_sizes
        
    except Exception as e:
        logger.warning(f"No se pudieron cargar tamaños del RAG: {e}")
    
    logger.info(f"📏 Usando tamaños por defecto: {_DEFAULT_SIZES}")
    return _DEFAULT_SIZES


def get_available_extras() -> list[str]:
    """
    Retorna los extras/adicionales disponibles.
    Intenta extraer del RAG, si no, usa valores por defecto.
    """
    try:
        docs = state["db"].similarity_search("extras adicionales pizza", k=5)
        extras = set()
        
        extra_patterns = [
            r"(queso\s+extra|doble\s+queso|orilla\s+de\s+queso|orilla\s+rellena)",
            r"(pepperoni\s+extra|tocino|champiñones|aceitunas|jalapeños)",
            r"(extra\s+queso|extra\s+pepperoni|bebida|refresco|postre)",
        ]
        
        for doc in docs:
            content_lower = doc.page_content.lower()
            for pattern in extra_patterns:
                matches = re.findall(pattern, content_lower)
                extras.update(matches)
        
        if extras:
            # Limpiar y capitalizar
            clean_extras = [e.title() for e in extras]
            logger.info(f"➕ Extras encontrados en RAG: {clean_extras}")
            return clean_extras
        
    except Exception as e:
        logger.warning(f"No se pudieron cargar extras del RAG: {e}")
    
    logger.info(f"➕ Usando extras por defecto: {_DEFAULT_EXTRAS}")
    return _DEFAULT_EXTRAS


def get_sizes_text() -> str:
    """Retorna los tamaños como texto formateado."""
    sizes = get_available_sizes()
    return ", ".join(sizes)


def get_extras_text() -> str:
    """Retorna los extras como texto formateado."""
    extras = get_available_extras()
    return ", ".join(extras)