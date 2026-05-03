from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Allow direct script execution without setting PYTHONPATH manually.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from researchpilot.search.arxiv_search import download_arxiv_paper
from researchpilot.search.arxiv_search import search_arxiv_papers


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Smoke test for arXiv search (optional first-paper PDF download).",
    )
    parser.add_argument("query", help="Search query for arXiv.")
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum number of arXiv results to return (default: 5).",
    )
    parser.add_argument(
        "--download-first",
        action="store_true",
        help="Download the first paper PDF to data/uploads/.",
    )
    return parser


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv[1:])

    query = (args.query or "").strip()
    if not query:
        print("Error: query is empty", file=sys.stderr)
        return 1

    try:
        papers = search_arxiv_papers(
            query=query,
            max_results=args.max_results,
            sort_by="relevance",
        )
    except Exception as exc:
        print(f"Error: failed to search arXiv: {exc}", file=sys.stderr)
        err_msg = str(exc)
        if "429" in err_msg or "rate limit" in err_msg.lower():
            print(
                "Error: arXiv rate limit hit. Please wait and retry later.",
                file=sys.stderr,
            )
        return 2

    print(f'query: "{query}"')
    print(f"results: {len(papers)}")

    if not papers:
        print("No results found.")
        return 0

    for rank, paper in enumerate(papers, start=1):
        summary_preview = str(paper.get("summary", "")).replace("\n", " ").strip()[:240]
        authors = ", ".join(paper.get("authors", []))
        print(f"rank={rank}")
        print(f"title={paper.get('title', '')}")
        print(f"authors={authors}")
        print(f"published={paper.get('published', '')}")
        print(f"pdf_url={paper.get('pdf_url', '')}")
        print(f"summary_preview={summary_preview}")
        if rank < len(papers):
            print("-" * 80)

    if args.download_first:
        try:
            saved_path = download_arxiv_paper(papers[0], output_dir="data/uploads")
            print(f"downloaded_pdf={saved_path}")
        except Exception as exc:
            print(f"Error: failed to download first PDF: {exc}", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
