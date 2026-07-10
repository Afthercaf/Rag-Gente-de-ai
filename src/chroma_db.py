# chroma_db.py - Wrapper para Qdrant (mantiene compatibilidad con código existente)

import logging
from typing import Any

from qdrant_db import QdrantVectorStore

logger = logging.getLogger(__name__)

# Singleton
_vector_store = None
_embedding_model = None


def get_vector_store(embedding_model):
    """Obtiene el vector store (singleton)"""
    global _vector_store, _embedding_model

    if _vector_store is None or _embedding_model != embedding_model:
        _embedding_model = embedding_model
        _vector_store = QdrantVectorStore(collection_name="pizzeria_docs")
        logger.info("Vector store inicializado")

    return _vector_store


def save_to_chroma_db(chunks, embedding_model):
    """Guarda documentos en Qdrant Cloud"""
    store = get_vector_store(embedding_model)
    return store.from_documents(chunks, embedding_model)


def get_retriever(embedding_model, k: int = 4):
    """Obtiene un retriever listo para usar"""
    store = get_vector_store(embedding_model)
    return store.as_retriever(embedding_model, search_kwargs={"k": k})