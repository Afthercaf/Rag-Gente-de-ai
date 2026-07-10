import logging
import os
import time
from typing import Any

from dotenv import load_dotenv
import httpx
from langchain_ollama import ChatOllama

from config.models_local import CHAT_MODEL_LOCAL
from providers.base_provider import BaseProvider

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://killerexpert10.tail29c8ce.ts.net:11434"
DEFAULT_RETRY_COUNT = 3
RETRY_BACKOFF_SECONDS = 0.5


class OllamaProvider(BaseProvider):
    """Proveedor local basado en Ollama REST. """

    def __init__(self, model_name: str | None = None, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)).rstrip("/")
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
        return httpx.Client(timeout=10.0)

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
