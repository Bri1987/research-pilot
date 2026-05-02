from researchpilot.retrieval.bm25_index import BM25Index
from researchpilot.retrieval.vector_index import VectorIndex
from researchpilot.schemas import DocumentChunk


class HybridRetriever:
    def __init__(
        self,
        bm25_weight: float = 0.45,
        vector_weight: float = 0.55,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self._bm25 = BM25Index()
        self._vector = VectorIndex(model_name=model_name)
        self._chunks: list[DocumentChunk] = []
        self._chunk_by_id: dict[str, DocumentChunk] = {}

    @staticmethod
    def _min_max_normalize(score_map: dict[str, float]) -> dict[str, float]:
        if not score_map:
            return {}

        values = list(score_map.values())
        min_score = min(values)
        max_score = max(values)

        if max_score == min_score:
            return {chunk_id: 1.0 for chunk_id in score_map}

        scale = max_score - min_score
        return {
            chunk_id: (score - min_score) / scale
            for chunk_id, score in score_map.items()
        }

    def build(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = list(chunks)
        self._chunk_by_id = {chunk.chunk_id: chunk for chunk in self._chunks}
        self._bm25.build(self._chunks)
        self._vector.build(self._chunks)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._chunks:
            return []
        if top_k <= 0:
            return []
        if not query or not query.strip():
            return []

        candidate_k = max(top_k * 3, 20)
        bm25_results = self._bm25.search(query, top_k=candidate_k)
        vector_results = self._vector.search(query, top_k=candidate_k)

        if not bm25_results and not vector_results:
            return []

        bm25_scores = {
            item["chunk_id"]: float(item["score"])
            for item in bm25_results
        }
        vector_scores = {
            item["chunk_id"]: float(item["score"])
            for item in vector_results
        }

        bm25_norm = self._min_max_normalize(bm25_scores)
        vector_norm = self._min_max_normalize(vector_scores)

        merged_ids = set(bm25_scores) | set(vector_scores)
        merged_results: list[dict] = []

        for chunk_id in merged_ids:
            chunk = self._chunk_by_id.get(chunk_id)
            if chunk is None:
                continue

            bm25_score = bm25_scores.get(chunk_id, 0.0)
            vector_score = vector_scores.get(chunk_id, 0.0)
            score = (
                self.bm25_weight * bm25_norm.get(chunk_id, 0.0)
                + self.vector_weight * vector_norm.get(chunk_id, 0.0)
            )

            merged_results.append(
                {
                    "score": float(score),
                    "bm25_score": float(bm25_score),
                    "vector_score": float(vector_score),
                    "chunk_id": chunk.chunk_id,
                    "paper_id": chunk.paper_id,
                    "page": chunk.page,
                    "text": chunk.text,
                }
            )

        merged_results.sort(
            key=lambda item: (
                item["score"],
                item["vector_score"],
                item["bm25_score"],
            ),
            reverse=True,
        )

        top_results = merged_results[:top_k]
        for rank, item in enumerate(top_results, start=1):
            item["rank"] = rank

        return top_results

    def list_papers(self) -> list[str]:
        return sorted({chunk.paper_id for chunk in self._chunks})

    def get_chunks_by_paper(self, paper_id: str) -> list[DocumentChunk]:
        return [chunk for chunk in self._chunks if chunk.paper_id == paper_id]
