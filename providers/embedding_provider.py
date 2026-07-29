# embedding_provider.py - Embeddings 100% LOCALES (sin Jina, sin APIs externas)
import logging
import os
from typing import Any, List

import core.config  # Carga centralizada del entorno.

from providers.huggingface_embeddings import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

# Modelo de embeddings local por defecto.
# all-MiniLM-L6-v2 ya viene cacheado localmente y produce vectores de 384
# dimensiones. Es un modelo general multilingüe suficiente para el RAG de
# la pizzería y NO requiere descarga ni conexión a Internet.
# Si se quiere mayor calidad en español, fijar en .env:
#   LOCAL_EMBEDDING_MODEL=intfloat/multilingual-e5-large
# (ese modelo sí debe descargarse una vez). El tamaño del vector se infiere
# automáticamente del modelo, así que no hay que tocar Qdrant.
DEFAULT_LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingProvider:
    """Proveedor de embeddings COMPLETAMENTE LOCAL.

    No realiza ninguna llamada HTTP ni depende de servicios externos
    (Jina fue eliminado por completo). Usa sentence-transformers
    (HuggingFace) para generar los vectores en la misma máquina.

    Garantía de no-caída: si el modelo local no puede cargarse (p.ej.
    falta el paquete o el modelo no está descargado), se registra el
    error y se propaga una excepción clara en el arranque — pero nunca
    se intenta contactar a un servicio remoto.
    """

    def __init__(self) -> None:
        self._model: Any = None
        self._model_name: str = os.getenv("LOCAL_EMBEDDING_MODEL") or DEFAULT_LOCAL_MODEL

    def get_model(self) -> Any:
        if self._model is None:
            try:
                logger.info("🚀 Cargando embeddings LOCALES: %s", self._model_name)
                self._model = HuggingFaceEmbeddings(self._model_name)
                logger.info("✅ Embeddings locales listos (%s)", self._model_name)
            except Exception as exc:
                logger.error("❌ No se pudo cargar el modelo de embeddings local: %s", exc, exc_info=True)
                raise
        return self._model

    @property
    def model_name(self) -> str:
        return self._model_name

    def embed(self, text: str, **kwargs: Any) -> List[float]:
        model = self.get_model()
        return model.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self.get_model()
        return model.embed_documents(texts)

    def dimension(self) -> int:
        """Devuelve la dimensión de los vectores del modelo local.

        Útil para configurar Qdrant/Chroma con el tamaño correcto sin
        hardcodear 1024 (que era el tamaño de Jina).
        """
        model = self.get_model()
        if hasattr(model, "dimension"):
            return model.dimension
        # Fallback: derivar de una consulta de prueba.
        sample = self.embed("dimension")
        return len(sample)
