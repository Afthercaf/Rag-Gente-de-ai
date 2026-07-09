from __future__ import annotations

import logging
from typing import List

logger = logging.getLogger(__name__)


class HuggingFaceEmbeddings:
    """Adaptador compatible con Chroma que expone embed_documents y embed_query."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return [list(map(float, vector)) for vector in vectors]

    def embed_query(self, text: str) -> List[float]:
        vector = self.model.encode([text], normalize_embeddings=True, convert_to_numpy=True)[0]
        return [float(value) for value in vector]
