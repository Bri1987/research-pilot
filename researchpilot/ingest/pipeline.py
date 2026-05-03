from pathlib import Path

from researchpilot.cards.paper_card_generator import generate_paper_card
from researchpilot.ingest.chunker import chunk_pages
from researchpilot.ingest.pdf_parser_pymupdf import parse_pdf
from researchpilot.qa.answer_with_citations import generate_answer_with_citations
from researchpilot.retrieval.hybrid_retriever import HybridRetriever
from researchpilot.review.lit_review_generator import generate_literature_review
from researchpilot.review.research_idea_generator import generate_research_ideas
from researchpilot.review.revised_review_generator import generate_revised_literature_review
from researchpilot.schemas import DocumentChunk
from researchpilot.storage.corpus_store import delete_cached_paper_card
from researchpilot.storage.corpus_store import get_cached_paper_card
from researchpilot.storage.corpus_store import set_cached_paper_card
from researchpilot.verify.claim_verifier import verify_review_claims


class ResearchPilotPipeline:
    def __init__(self):
        self.retriever = HybridRetriever()
        self._chunks: list[DocumentChunk] = []

    def ingest_pdf(self, pdf_path: str, paper_id: str | None = None):
        resolved_paper_id = paper_id or Path(pdf_path).stem
        had_existing_paper = any(
            chunk.paper_id == resolved_paper_id for chunk in self._chunks
        )

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
        # Expose chunks for source-aware claim verification retrieval.
        self.retriever.chunks = list(self._chunks)
        # Invalidate stale paper-card cache only when the same paper is re-ingested
        # within the current session. This keeps cross-session cache usable.
        if had_existing_paper:
            delete_cached_paper_card(resolved_paper_id)

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
        cached_card = get_cached_paper_card(paper_id)
        if cached_card is not None:
            return cached_card

        chunks = self.retriever.get_chunks_by_paper(paper_id)
        card = generate_paper_card(
            paper_id=paper_id,
            chunks=chunks,
        )
        set_cached_paper_card(paper_id, card)
        return card

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
        top_k: int = 5,
        verification_mode: str = "balanced",
        diversify_evidence: bool = True,
        max_per_paper: int = 2,
        source_first: bool = True,
        source_only_when_available: bool = True,
        paper_cards: dict[str, dict] | None = None,
    ) -> list[dict]:
        return verify_review_claims(
            review_text=review_text,
            retriever=self.retriever,
            top_k=top_k,
            verification_mode=verification_mode,
            diversify_evidence=diversify_evidence,
            max_per_paper=max_per_paper,
            source_first=source_first,
            source_only_when_available=source_only_when_available,
            paper_cards=paper_cards,
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

    def generate_research_ideas(
        self,
        topic: str | None,
        paper_cards: dict[str, dict],
        literature_review: str | None,
        revised_literature_review: str | None,
        claim_verification: list[dict] | None,
        num_ideas: int = 5,
    ) -> str:
        return generate_research_ideas(
            topic=topic,
            paper_cards=paper_cards,
            literature_review=literature_review,
            revised_literature_review=revised_literature_review,
            claim_verification=claim_verification,
            num_ideas=num_ideas,
        )
