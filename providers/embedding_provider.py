# embedding_provider.py - Versión solo Jina
import logging
import os
from typing import Any, List

from dotenv import load_dotenv
from langchain_core.embeddings import FakeEmbeddings

from providers.jina_embeddings import JinaEmbeddings

load_dotenv()

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Proveedor de embeddings con Jina AI v3 (sin fallback a HuggingFace)"""

    def __init__(self) -> None:
        self._model: Any = None
        self._fallback_model: FakeEmbeddings | None = None
        self._embedding_size = 1024

    def get_model(self) -> Any:
        if self._model is None:
            try:
                logger.info("🚀 Inicializando Jina Embeddings v3")
                self._model = JinaEmbeddings()
                logger.info("✅ Jina Embeddings listo")
            except Exception as exc:
                logger.error("❌ No se pudo cargar Jina embeddings: %s", exc, exc_info=True)
                logger.warning("⚠️ Usando FakeEmbeddings como fallback")
                self._model = self.get_fallback_model()
        return self._model

    def get_fallback_model(self) -> FakeEmbeddings:
        if self._fallback_model is None:
            self._fallback_model = FakeEmbeddings(size=self._embedding_size)
        return self._fallback_model

    def _apply_prefix(self, text: str, is_query: bool) -> str:
        prefix = "search_query:" if is_query else "search_document:"
        return f"{prefix}{text}"

    def embed(self, text: str, **kwargs: Any) -> List[float]:
        try:
            model = self.get_model()
            return model.embed_query(self._apply_prefix(text, is_query=True))
        except Exception as exc:
            logger.warning("Embedding falló; usando fallback: %s", exc)
            return self.get_fallback_model().embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            model = self.get_model()
            prefixed = [self._apply_prefix(t, is_query=False) for t in texts]
            return model.embed_documents(prefixed)
        except Exception as exc:
            logger.warning("Embedding documents falló; usando fallback: %s", exc)
            return self.get_fallback_model().embed_documents(texts)