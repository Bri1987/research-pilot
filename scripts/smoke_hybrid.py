from pathlib import Path
import sys

# Allow direct script execution without setting PYTHONPATH manually.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from researchpilot.ingest.chunker import chunk_pages
from researchpilot.ingest.pdf_parser_pymupdf import parse_pdf
from researchpilot.retrieval.hybrid_retriever import HybridRetriever


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            'Usage: python scripts/smoke_hybrid.py path/to/file.pdf "query text"',
            file=sys.stderr,
        )
        return 1

    pdf_path = argv[1]
    query = " ".join(argv[2:]).strip()
    paper_id = Path(pdf_path).stem

    if not query:
        print("Error: query is empty", file=sys.stderr)
        return 1

    try:
        pages = parse_pdf(pdf_path)
        chunks = chunk_pages(pages=pages, paper_id=paper_id, title=paper_id)

        retriever = HybridRetriever()
        retriever.build(chunks)
        results = retriever.search(query, top_k=5)

        print(f"parsed pages: {len(pages)}")
        print(f"chunks: {len(chunks)}")
        print(f'query: "{query}"')
        print("top_k: 5")

        if not results:
            print("No results.")
            return 0

        for item in results:
            preview = item["text"][:200]
            print(
                f'rank={item["rank"]} '
                f'score={item["score"]:.4f} '
                f'bm25_score={item["bm25_score"]:.4f} '
                f'vector_score={item["vector_score"]:.4f} '
                f'paper_id={item["paper_id"]} '
                f'page={item["page"]} '
                f"text_preview={preview}"
            )

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
