import logging
from typing import Any

from providers import GroqProvider, LocalProvider, EmbeddingProvider
from utils.constants import USE_LOCAL

logger = logging.getLogger(__name__)


class ProviderService:
    """Selector centralizado de proveedores."""

    def __init__(self) -> None:
        self.use_local = USE_LOCAL
        self.llm_provider = LocalProvider() if self.use_local else GroqProvider()
        self.embedding_provider = EmbeddingProvider()
        logger.info(
            "Proveedor LLM seleccionado: %s",
            "Ollama local" if self.use_local else "Groq remoto",
        )

    def generate(self, prompt: Any, **kwargs: Any) -> Any:
        try:
            return self.llm_provider.generate(prompt, **kwargs)
        except Exception as exc:
            logger.exception("Fallo en proveedor LLM: %s", exc)
            raise

    def stream(self, prompt: Any, **kwargs: Any) -> Any:
        return self.llm_provider.stream(prompt, **kwargs)

    def embed(self, text: str, **kwargs: Any) -> list[float]:
        return self.embedding_provider.embed(text, **kwargs)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embedding_provider.embed_documents(texts)

    def health(self) -> bool:
        return self.llm_provider.health()


provider_service = ProviderService()
