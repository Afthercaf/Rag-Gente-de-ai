import logging
import os
from typing import Any, List

from dotenv import load_dotenv
from langchain_ollama import OllamaEmbeddings
from langchain_core.embeddings import FakeEmbeddings

load_dotenv()

from config.models import EMBED_MODEL as REMOTE_EMBED_MODEL
from config.models_local import EMBED_MODEL_LOCAL
from utils.constants import OLLAMA_BASE_URL, USE_LOCAL

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """Proveedor de embeddings compatible con Chroma y Ollama."""

    def __init__(self) -> None:
        self._model: OllamaEmbeddings | FakeEmbeddings | None = None
        self._fallback_model: FakeEmbeddings | None = None
        self._model_name = (
            os.getenv("EMBED_MODEL_LOCAL", EMBED_MODEL_LOCAL)
            if USE_LOCAL
            else os.getenv("EMBED_MODEL", REMOTE_EMBED_MODEL)
        )
        self._base_url = os.getenv("OLLAMA_BASE_URL", OLLAMA_BASE_URL)

    def get_model(self) -> Any:
        if self._model is None:
            logger.info("Usando proveedor de embeddings Ollama: %s", self._model_name)
            try:
                self._model = OllamaEmbeddings(model=self._model_name, base_url=self._base_url)
            except Exception as exc:
                logger.warning("No se pudo cargar embeddings Ollama: %s", exc, exc_info=True)
                self._model = self.get_fallback_model()
        return self._model

    def get_fallback_model(self) -> FakeEmbeddings:
        if self._fallback_model is None:
            self._fallback_model = FakeEmbeddings(size=384)
        return self._fallback_model

    def _encode(self, texts: List[str]) -> List[List[float]]:
        model = self.get_model()
        if hasattr(model, "embed_documents"):
            return [list(map(float, vector)) for vector in model.embed_documents(texts)]
        if hasattr(model, "embed_query"):
            return [list(map(float, model.embed_query(text))) for text in texts]
        if hasattr(model, "encode"):
            vectors = model.encode(texts, normalize_embeddings=True)
            return [list(map(float, vector)) for vector in vectors]
        raise NotImplementedError("El modelo de embeddings no soporta codificación")

    def embed(self, text: str, **kwargs: Any) -> List[float]:
        try:
            return self._encode([self._apply_prefix(text, is_query=True)])[0]
        except Exception as exc:
            logger.warning("El embedding falló; usando fallback sintético: %s", exc, exc_info=True)
            return self.get_fallback_model().embed_query(self._apply_prefix(text, is_query=True))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._encode([self._apply_prefix(text, is_query=False) for text in texts])
        except Exception as exc:
            logger.warning("La generación de embeddings falló; usando fallback sintético: %s", exc, exc_info=True)
            prefixed = [self._apply_prefix(text, is_query=False) for text in texts]
            return self.get_fallback_model().embed_documents(prefixed)

    def _apply_prefix(self, text: str, is_query: bool) -> str:
        prefix = "search_query:" if is_query else "search_document:"
        return f"{prefix}{text}"
