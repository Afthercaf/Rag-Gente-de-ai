import asyncio

from core.state import state
from utils.constants import TOP_K


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
