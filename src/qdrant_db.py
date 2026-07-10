# src/qdrant_db.py
import logging
import os
from typing import List, Optional

from langchain_community.vectorstores import Qdrant
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Conexión a Qdrant Cloud"""

    def __init__(self, collection_name: str = "pizzeria_docs", vector_size: int = 1024):
        self.url = os.getenv("QDRANT_URL")
        self.api_key = os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name
        # Jina Embeddings v3 devuelve vectores de 1024 dimensiones
        # (ver EmbeddingProvider._embedding_size). Si cambiás de modelo
        # de embeddings, actualizá este valor.
        self.vector_size = vector_size

        if not self.url or not self.api_key:
            raise ValueError("QDRANT_URL y QDRANT_API_KEY son requeridas")

        logger.info(f"Conectando a Qdrant: {self.url}")
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=60,
        )

    def _ensure_collection(self) -> bool:
        """
        Crea la colección manualmente si no existe, usando el cliente
        low-level de qdrant (client.create_collection).

        🔥 FIX: NO usamos Qdrant.from_documents() para crear la colección.
        Ese wrapper de langchain_community arma internamente un argumento
        `init_from` y se lo pasa siempre a client.recreate_collection(),
        sin importar el valor de `force_recreate` que le pases. Las
        versiones recientes de qdrant-client ya no aceptan ese argumento
        y el proceso muere con:
            AssertionError: Unknown arguments: ['init_from']
        Creando la colección nosotros mismos evitamos ese código roto
        por completo.
        """
        collections = self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)

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
        """Crea la colección si hace falta y agrega documentos."""
        try:
            existed = self._ensure_collection()

            vector_store = Qdrant(
                client=self.client,
                collection_name=self.collection_name,
                embeddings=embedding_model,
            )
            vector_store.add_documents(documents)

            if existed:
                logger.info(f"✅ Documentos agregados a colección existente: {self.collection_name}")
            else:
                logger.info(f"✅ Colección creada y documentos agregados: {self.collection_name}")

            return vector_store

        except Exception as exc:
            logger.error(f"❌ Error en Qdrant: {exc}", exc_info=True)
            raise

    def as_retriever(self, embedding_model, search_kwargs: Optional[dict] = None):
        """Retriever para búsqueda semántica"""
        vector_store = Qdrant(
            client=self.client,
            collection_name=self.collection_name,
            embeddings=embedding_model,
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