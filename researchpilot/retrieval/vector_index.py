import numpy as np
from sentence_transformers import SentenceTransformer

from researchpilot.schemas import DocumentChunk


class VectorIndex:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model: SentenceTransformer | None = None
        self._chunks: list[DocumentChunk] = []
        self._embeddings: np.ndarray | None = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def build(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = list(chunks)
        if not self._chunks:
            self._embeddings = None
            return

        model = self._get_model()
        texts = [chunk.text for chunk in self._chunks]
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        self._embeddings = embeddings.astype(np.float32, copy=False)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._chunks or self._embeddings is None:
            return []
        if top_k <= 0:
            return []
        if not query or not query.strip():
            return []

        model = self._get_model()
        query_embedding = model.encode(
            query,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype(np.float32, copy=False)

        scores = self._embeddings @ query_embedding
        top_n = min(top_k, len(self._chunks))
        top_indices = np.argsort(scores)[::-1][:top_n]

        results: list[dict] = []
        for rank, idx in enumerate(top_indices, start=1):
            chunk = self._chunks[int(idx)]
            results.append(
                {
                    "rank": rank,
                    "score": float(scores[idx]),
                    "chunk_id": chunk.chunk_id,
                    "paper_id": chunk.paper_id,
                    "page": chunk.page,
                    "text": chunk.text,
                }
            )

        return results
