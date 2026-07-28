# src/qdrant_db.py
import logging
import os
from typing import Optional

from langchain_qdrant import QdrantVectorStore as LangchainQdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)

# Solo se exporta el wrapper propio; evita que otros módulos importen
# por error la clase original de langchain_qdrant desde este archivo.
__all__ = ["QdrantVectorStoreWrapper"]


class QdrantVectorStoreWrapper:
    """Conexión a Qdrant Cloud"""

    def __init__(self, collection_name: str = "pizzeria_docs", vector_size: int | None = None):
        self.url = os.getenv("QDRANT_URL")
        self.api_key = os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name
        # El tamaño del vector se deduce del modelo de embeddings LOCAL en
        # uso (ya no se hardcodea 1024, que era el tamaño de Jina). Si no
        # se pasa, se infiere del proveedor de embeddings configurado.
        if vector_size is None:
            try:
                from services.provider_service import provider_service
                vector_size = provider_service.embedding_provider.dimension()
            except Exception:
                vector_size = 1024
        self.vector_size = int(vector_size)

        if not self.url or not self.api_key:
            raise ValueError("QDRANT_URL y QDRANT_API_KEY son requeridas")

        logger.info("Conectando a Qdrant Cloud")
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=60,
        )

    def _ensure_collection(self, recreate: bool = False) -> bool:
        """
        Crea la colección manualmente si no existe, usando el cliente
        low-level de qdrant (client.create_collection).

        Seguimos creando la colección a mano (en vez de dejar que el
        wrapper de langchain la cree) para tener control total y evitar
        sorpresas si langchain_qdrant cambia su comportamiento interno
        en el futuro.

        FIX (duplicados): si `recreate=True` y la colección ya existe,
        se borra y se vuelve a crear vacía. Esto es necesario porque
        `from_documents()` antes insertaba los mismos chunks del PDF
        en CADA reinicio del servicio, sin verificar si ya estaban
        cargados — el resultado, tras varios restarts, era una
        colección con múltiples copias idénticas del mismo chunk. Eso
        hacía que `similarity_search` devolviera duplicados del mismo
        bloque en vez de diversidad de contenido, dejando afuera del
        top-k otros chunks igual de relevantes (ej. el precio de
        varias pizzas del menú quedaba sin recuperarse porque los
        slots del top-k estaban ocupados por copias repetidas de un
        único chunk).
        """
        collections = self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)

        if exists and recreate:
            logger.info(
                f"Recreando colección '{self.collection_name}' desde cero "
                f"(evita duplicados acumulados de cargas anteriores)"
            )
            self.client.delete_collection(self.collection_name)
            exists = False

        if not exists:
            logger.info(
                f"Creando colección '{self.collection_name}' ({self.vector_size} dims, cosine)"
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=self.vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )

        return exists

    def from_documents(self, documents, embedding_model):
        """
        Recrea la colección desde cero y carga los documentos actuales.

        FIX: antes reutilizaba la colección existente y solo agregaba
        (`add_documents`) encima — sin dedup ni verificación de que ya
        estuviera cargada. En cada restart del servicio se repetía la
        carga completa del PDF, acumulando copias idénticas de los
        mismos 18 chunks. Ahora siempre se parte de una colección
        vacía, así el índice queda 1:1 con los documentos actuales del
        PDF, sin importar cuántas veces se reinicie el servicio.
        """
        try:
            self._ensure_collection(recreate=True)

            vector_store = LangchainQdrantVectorStore(
                client=self.client,
                collection_name=self.collection_name,
                embedding=embedding_model,  # 👈 ojo: singular, no "embeddings"
            )
            vector_store.add_documents(documents)

            logger.info(
                f"✅ Colección recreada y {len(documents)} documentos cargados: "
                f"{self.collection_name}"
            )

            return vector_store

        except Exception as exc:
            logger.error(f"❌ Error en Qdrant: {exc}", exc_info=True)
            raise

    def as_retriever(self, embedding_model, search_kwargs: Optional[dict] = None):
        """Retriever para búsqueda semántica"""
        vector_store = LangchainQdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=embedding_model,  # 👈 ojo: singular, no "embeddings"
        )
        default_kwargs = {"k": 4, "score_threshold": 0.7}
        if search_kwargs:
            default_kwargs.update(search_kwargs)
        return vector_store.as_retriever(search_kwargs=default_kwargs)

    def delete_collection(self):
        """Elimina la colección"""
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"🗑️ Colección {self.collection_name} eliminada")
        except Exception as exc:
            logger.warning(f"No se pudo eliminar: {exc}")