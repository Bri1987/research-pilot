from pathlib import Path

from researchpilot.cards.paper_card_generator import generate_paper_card
from researchpilot.ingest.chunker import chunk_pages
from researchpilot.ingest.pdf_parser_pymupdf import parse_pdf
from researchpilot.qa.answer_with_citations import generate_answer_with_citations
from researchpilot.retrieval.hybrid_retriever import HybridRetriever
from researchpilot.review.lit_review_generator import generate_literature_review
from researchpilot.review.revised_review_generator import generate_revised_literature_review
from researchpilot.schemas import DocumentChunk
from researchpilot.verify.claim_verifier import verify_review_claims


class ResearchPilotPipeline:
    def __init__(self):
        self.retriever = HybridRetriever()
        self._chunks: list[DocumentChunk] = []

    def ingest_pdf(self, pdf_path: str, paper_id: str | None = None):
        resolved_paper_id = paper_id or Path(pdf_path).stem

        pages = parse_pdf(pdf_path)
        new_chunks = chunk_pages(
            pages=pages,
            paper_id=resolved_paper_id,
            title=resolved_paper_id,
        )

        # Replace previously ingested chunks for the same paper_id.
        self._chunks = [
            chunk for chunk in self._chunks if chunk.paper_id != resolved_paper_id
        ]
        self._chunks.extend(new_chunks)
        self.retriever.build(self._chunks)

        return new_chunks

    def ask(self, question: str, top_k: int = 8) -> dict:
        evidence = self.retriever.search(question, top_k=top_k)
        answer = generate_answer_with_citations(
            question=question,
            evidence=evidence,
        )
        return {
            "answer": answer,
            "evidence": evidence,
        }

    def list_papers(self) -> list[str]:
        return self.retriever.list_papers()

    def build_paper_card(self, paper_id: str) -> dict:
        chunks = self.retriever.get_chunks_by_paper(paper_id)
        return generate_paper_card(
            paper_id=paper_id,
            chunks=chunks,
        )

    def write_literature_review(
        self,
        topic: str,
        paper_cards: dict[str, dict],
    ) -> str:
        return generate_literature_review(
            topic=topic,
            paper_cards=paper_cards,
        )

    def verify_literature_review(
        self,
        review_text: str,
        top_k: int = 4,
    ) -> list[dict]:
        return verify_review_claims(
            review_text=review_text,
            retriever=self.retriever,
            top_k=top_k,
        )

    def rewrite_literature_review(
        self,
        original_review: str,
        claim_verification: list[dict],
    ) -> str:
        return generate_revised_literature_review(
            original_review=original_review,
            claim_verification=claim_verification,
        )
