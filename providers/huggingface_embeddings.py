from __future__ import annotations

import logging
from typing import List

from langchain_core.embeddings import Embeddings

logger = logging.getLogger(__name__)


class HuggingFaceEmbeddings(Embeddings):
    """Embeddings 100% LOCALES usando sentence-transformers.

    Hereda de `langchain_core.embeddings.Embeddings` (la interfaz oficial
    de LangChain), por lo que es 100% compatible con LangchainQdrantVectorStore
    y cualquier otro componente de LangChain que espere un `Embeddings`.

    NO realiza ninguna llamada de red: el modelo se ejecuta localmente.
    """

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    @property
    def dimension(self) -> int:
        """Dimensión de los vectores del modelo (la infiere del modelo)."""
        if hasattr(self.model, "get_embedding_dimension"):
            return int(self.model.get_embedding_dimension())
        return int(self.model.get_sentence_embedding_dimension())

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return [list(map(float, vector)) for vector in vectors]

    def embed_query(self, text: str) -> List[float]:
        vector = self.model.encode([text], normalize_embeddings=True, convert_to_numpy=True)[0]
        return [float(value) for value in vector]
