from pathlib import Path

import fitz

from researchpilot.schemas import PageText


def parse_pdf(pdf_path: str) -> list[PageText]:
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file, got: {pdf_path}")

    try:
        with fitz.open(str(path)) as doc:
            pages: list[PageText] = []
            for page_number, page in enumerate(doc, start=1):
                text = page.get_text("text")
                if not text or not text.strip():
                    continue
                pages.append(PageText(page=page_number, text=text))
            return pages
    except Exception as exc:
        raise RuntimeError(f"Failed to open PDF '{pdf_path}': {exc}") from exc
