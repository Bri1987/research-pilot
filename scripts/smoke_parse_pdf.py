from pathlib import Path
import sys

# Allow direct script execution without setting PYTHONPATH manually.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from researchpilot.ingest.chunker import chunk_pages
from researchpilot.ingest.pdf_parser_pymupdf import parse_pdf


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: python scripts/smoke_parse_pdf.py path/to/file.pdf", file=sys.stderr)
        return 1

    pdf_path = argv[1]
    paper_id = Path(pdf_path).stem

    try:
        pages = parse_pdf(pdf_path)
        chunks = chunk_pages(pages=pages, paper_id=paper_id, title=paper_id)

        print(f"parsed pages: {len(pages)}")
        print(f"chunks: {len(chunks)}")

        if chunks:
            first = chunks[0]
            preview = first.text[:200]
            print(
                "first chunk: "
                f"paper_id={first.paper_id}, "
                f"page={first.page}, "
                f"text_preview={preview}"
            )
        else:
            print("first chunk: <none>")

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
