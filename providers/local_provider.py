from typing import Any

from providers.ollama_provider import OllamaProvider
from config.models_local import CHAT_MODEL_LOCAL


class LocalProvider(OllamaProvider):
    """Proveedor local legacy que reutiliza OllamaProvider."""

    def __init__(self, model_name: str | None = None) -> None:
        super().__init__(model_name=model_name or CHAT_MODEL_LOCAL)

    def embed(self, text: str, **kwargs: Any) -> list[float]:
        raise NotImplementedError("Los embeddings locales se manejan por separado")
