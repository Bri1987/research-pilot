import re

from rank_bm25 import BM25Okapi

from researchpilot.schemas import DocumentChunk


class BM25Index:
    def __init__(self):
        self._chunks: list[DocumentChunk] = []
        self._bm25: BM25Okapi | None = None

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9_]+", text.lower())

    def build(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = list(chunks)
        if not self._chunks:
            self._bm25 = None
            return

        corpus_tokens = [self._tokenize(chunk.text) for chunk in self._chunks]
        self._bm25 = BM25Okapi(corpus_tokens)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._chunks or self._bm25 is None:
            return []
        if top_k <= 0:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        results: list[dict] = []
        for rank, (chunk_idx, score) in enumerate(ranked, start=1):
            chunk = self._chunks[chunk_idx]
            results.append(
                {
                    "rank": rank,
                    "score": float(score),
                    "chunk_id": chunk.chunk_id,
                    "paper_id": chunk.paper_id,
                    "page": chunk.page,
                    "text": chunk.text,
                }
            )

        return results
