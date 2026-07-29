import logging
import os
import time
from typing import Any
from urllib.parse import urlsplit

import core.config  # Carga centralizada del entorno.
from core.config import require_env
import httpx
from langchain_ollama import ChatOllama

from config.models_local import CHAT_MODEL_LOCAL
from providers.base_provider import BaseProvider

logger = logging.getLogger(__name__)

DEFAULT_RETRY_COUNT = 3
RETRY_BACKOFF_SECONDS = 0.5


def _validated_ollama_url(raw_url: str) -> str:
    """Valida el destino Ollama con una allowlist de egress tipo CORS."""
    parsed = urlsplit(raw_url.strip())
    allowed_hosts = {
        host.strip().lower()
        for host in require_env("OLLAMA_ALLOWED_HOSTS").split(",")
        if host.strip()
    }
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.hostname.lower() not in allowed_hosts
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise RuntimeError(
            "OLLAMA_BASE_URL no pertenece a un host Ollama permitido."
        )
    if parsed.port not in {None, 443, 11434}:
        raise RuntimeError("El puerto de OLLAMA_BASE_URL no está permitido.")
    return raw_url.strip().rstrip("/")


class OllamaProvider(BaseProvider):
    """Proveedor local basado en Ollama REST. """

    def __init__(self, model_name: str | None = None, base_url: str | None = None) -> None:
        self.base_url = _validated_ollama_url(
            base_url or require_env("OLLAMA_BASE_URL")
        )
        self.model_name = model_name or os.getenv("CHAT_MODEL_LOCAL", CHAT_MODEL_LOCAL)
        self._model: ChatOllama | None = None

    def get_model(self) -> ChatOllama:
        if self._model is None:
            logger.info("Usando proveedor Ollama local")
            logger.info("Servidor: %s", self.base_url)
            logger.info("Modelo: %s", self.model_name)
            self._model = ChatOllama(
                model=self.model_name,
                base_url=self.base_url,
                temperature=0.2,
                num_ctx=4096,
                num_predict=512,
                repeat_penalty=1.1,
                top_k=40,
                top_p=0.9,
                validate_model_on_init=False,
            )
        return self._model

    def _http_client(self) -> httpx.Client:
        return httpx.Client(
            timeout=10.0,
            follow_redirects=False,
            trust_env=False,
        )

    def _check_tags_endpoint(self) -> bool:
        try:
            url = f"{self.base_url}/api/tags"
            logger.debug("Consultando Ollama /api/tags: %s", url)
            with self._http_client() as client:
                response = client.get(url)
            response.raise_for_status()
            logger.debug("Ollama /api/tags devolvió %s", response.status_code)
            return True
        except Exception as exc:
            logger.warning("Error al comprobar /api/tags: %s", exc)
            return False

    def _check_generate_endpoint(self) -> bool:
        try:
            url = f"{self.base_url}/api/generate"
            payload = {"model": self.model_name, "prompt": "Hola", "max_tokens": 1}
            logger.debug("Consultando Ollama /api/generate: %s", url)
            with self._http_client() as client:
                response = client.post(url, json=payload)
            response.raise_for_status()
            logger.debug("Ollama /api/generate devolvió %s", response.status_code)
            return True
        except Exception as exc:
            logger.warning("Error al comprobar /api/generate: %s", exc)
            return False

    def _diagnose_ollama(self) -> None:
        logger.warning("Diagnóstico Ollama iniciado para %s", self.base_url)
        self._check_tags_endpoint()
        self._check_generate_endpoint()

    def generate(self, prompt: Any, **kwargs: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, DEFAULT_RETRY_COUNT + 1):
            try:
                logger.info("Intento %s/%s en Ollama para el modelo %s", attempt, DEFAULT_RETRY_COUNT, self.model_name)
                start = time.time()
                response = self.get_model().invoke(prompt, **kwargs)
                duration = time.time() - start
                logger.info("Ollama respondió en %.2fs", duration)
                return response
            except Exception as exc:
                last_error = exc
                logger.warning("Ollama intentó y falló [%s/%s]: %s", attempt, DEFAULT_RETRY_COUNT, exc, exc_info=True)
                if attempt < DEFAULT_RETRY_COUNT:
                    time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                    continue
                self._diagnose_ollama()
                raise RuntimeError(
                    "Ollama no pudo completar la solicitud. Verifica que el servidor local de Ollama esté activo en "
                    f"{self.base_url} y que el modelo '{self.model_name}' esté disponible. Detalle: {exc}"
                ) from exc

    def stream(self, prompt: Any, **kwargs: Any) -> Any:
        try:
            return self.get_model().stream(prompt, **kwargs)
        except Exception as exc:
            logger.error("Ollama stream falló: %s", exc, exc_info=True)
            self._diagnose_ollama()
            raise

    def embed(self, text: str, **kwargs: Any) -> list[float]:
        raise NotImplementedError("OllamaProvider no maneja embeddings. Usa EmbeddingProvider.")

    def health(self) -> bool:
        if not self._check_tags_endpoint():
            return False
        try:
            self.get_model()
            return True
        except Exception as exc:
            logger.warning("Ollama provider no disponible: %s", exc)
            return False

    def invoke(self, prompt: Any, **kwargs: Any) -> Any:
        return self.generate(prompt, **kwargs)
