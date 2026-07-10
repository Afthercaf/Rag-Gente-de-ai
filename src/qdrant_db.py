# src/qdrant_db.py
import logging
import os
from typing import List, Optional

from langchain_community.vectorstores import Qdrant
from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Conexión a Qdrant Cloud"""

    def __init__(self, collection_name: str = "pizzeria_docs"):
        self.url = os.getenv("QDRANT_URL")
        self.api_key = os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name

        if not self.url or not self.api_key:
            raise ValueError("QDRANT_URL y QDRANT_API_KEY son requeridas")

        logger.info(f"Conectando a Qdrant: {self.url}")
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            timeout=60,
        )

    def from_documents(self, documents, embedding_model):
        """Crea o actualiza la colección"""
        try:
            # Verificar si la colección existe
            collections = self.client.get_collections()
            exists = any(c.name == self.collection_name for c in collections.collections)

            # 🔥 FIX: No pasar force_recreate para evitar init_from
            if exists:
                # Si existe, usarla sin recrear
                vector_store = Qdrant(
                    client=self.client,
                    collection_name=self.collection_name,
                    embeddings=embedding_model,
                )
                # Agregar documentos a la colección existente
                vector_store.add_documents(documents)
                logger.info(f"✅ Documentos agregados a colección existente: {self.collection_name}")
                return vector_store
            else:
                # Si no existe, crearla
                vector_store = Qdrant.from_documents(
                    documents=documents,
                    embedding=embedding_model,
                    url=self.url,
                    api_key=self.api_key,
                    collection_name=self.collection_name,
                    force_recreate=False,  # 🔥 No recrear si existe
                )
                logger.info(f"✅ Colección creada: {self.collection_name}")
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