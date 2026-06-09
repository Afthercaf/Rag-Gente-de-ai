import asyncio
import time

from langchain_ollama import OllamaEmbeddings

from core.state import state
from prompts.pizza_prompt import pizza_prompt
from src.chroma_db import save_to_chroma_db
from src.file_processor import chunk_pdfs
from src.supabase_promos import load_promotions
from utils.constants import EMBED_MODEL


async def load_resources_background() -> None:
    """Carga todos los recursos de la aplicación en segundo plano."""
    print("🔄 Iniciando carga de recursos en background...")
    start_time = time.time()

    try:
        # 1. Promociones desde Supabase
        print("📢 Cargando promociones...")
        state["promo_documents"] = await asyncio.to_thread(load_promotions)
        print(f"✅ Promociones cargadas: {len(state['promo_documents'])}")

        # 2. Modelo de embeddings
        print("🔤 Cargando modelo de embeddings...")
        state["embedding_model"] = await asyncio.to_thread(
            OllamaEmbeddings,
            model=EMBED_MODEL,
        )
        print("✅ Modelo de embeddings listo")

        # 3. PDFs → ChromaDB
        print("📄 Procesando documentos...")
        pdf_documents = await asyncio.to_thread(chunk_pdfs)
        state["db"] = await asyncio.to_thread(
            save_to_chroma_db,
            pdf_documents,
            state["embedding_model"],
        )
        print("✅ ChromaDB lista")

        # 4. Prompt template
        state["prompt_template"] = pizza_prompt

        # 5. El modelo LLM se carga en lazy (primer uso)
        state["ready"] = True
        print(f"✅ API lista en {time.time() - start_time:.2f}s")

    except Exception as e:
        import traceback
        print(f"❌ Error cargando recursos: {e}")
        traceback.print_exc()
        state["ready"] = False
