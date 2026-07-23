import asyncio
import time

from core.state import state
from prompts.pizza_prompt import pizza_prompt
from src.chroma_db import save_to_chroma_db
from src.file_processor import chunk_pdfs
from src.supabase_promos import load_promotions
from services.provider_service import provider_service


async def _load_vector_store_with_retry(max_attempts: int = 5) -> None:
    """Carga ChromaDB/Qdrant reintentando, sin bloquear la API.

    Si el proveedor de embeddings local falla al inicio (p.ej. el modelo
    no está descargado), el proceso de carga se reintenta en segundo
    plano. La API se marca 'ready' de todos modos para que el chat
    funcione (con RAG degradado) en vez de quedar bloqueada para siempre
    devolviendo 'inicializando...'.
    """
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            pdf_documents = await asyncio.to_thread(chunk_pdfs)
            state["db"] = await asyncio.to_thread(
                save_to_chroma_db,
                pdf_documents,
                state["embedding_model"],
            )
            logger_loaded()
            return
        except Exception as exc:  # noqa: BLE001
            import traceback
            last_error = exc
            print(f"⚠️ Intento {attempt}/{max_attempts} de carga de vector store falló: {exc}")
            traceback.print_exc()
            await asyncio.sleep(5 * attempt)
    # Agotados los reintentos: dejamos la API usable sin RAG.
    print(f"❌ No se pudo cargar el vector store tras {max_attempts} intentos: {last_error}")
    print("⚠️ API continuará SIN RAG (búsqueda semántica degradada).")


def logger_loaded() -> None:
    print("✅ ChromaDB lista")


async def load_resources_background() -> None:
    """Carga todos los recursos de la aplicación en segundo plano."""
    print("🔄 Iniciando carga de recursos en background...")
    start_time = time.time()

    try:
        # 1. Promociones desde Supabase
        print("📢 Cargando promociones...")
        state["promo_documents"] = await asyncio.to_thread(load_promotions)
        print(f"✅ Promociones cargadas: {len(state['promo_documents'])}")

        # 2. Modelo de embeddings LOCAL (sentence-transformers, sin APIs externas)
        print("🔤 Cargando modelo de embeddings local...")
        state["embedding_model"] = provider_service.embedding_provider.get_model()
        print("✅ Modelo de embeddings local listo")

        # 3. PDFs → Vector store (reintenta; no bloquea la API si falla)
        await _load_vector_store_with_retry()

        # 4. Prompt template
        state["prompt_template"] = pizza_prompt

        # 5. El modelo LLM se carga en lazy (primer uso)
        state["ready"] = True
        print(f"✅ API lista en {time.time() - start_time:.2f}s")

    except Exception as e:  # noqa: BLE001
        import traceback
        print(f"❌ Error cargando recursos: {e}")
        traceback.print_exc()
        # No dejamos la API bloqueada: marcamos lista de todas formas para
        # que el chat responda (sin RAG) en lugar de devolver 500 siempre.
        state["ready"] = True
