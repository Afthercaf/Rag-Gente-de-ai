import logging
import os
from typing import List

import httpx
from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


class JinaEmbeddings(Embeddings):
    """Embeddings usando Jina AI v3"""

    def __init__(self):
        self.api_key = os.getenv("JINA_API_KEY")
        if not self.api_key:
            raise ValueError("JINA_API_KEY no configurada")
        self.url = "https://api.jina.ai/v1/embeddings"
        self.model = "jina-embeddings-v3"

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            response = httpx.post(
                self.url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": texts,
                    "encoding_format": "float",
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]
        except Exception as exc:
            logger.error("Error en Jina embeddings: %s", exc, exc_info=True)
            raise

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]