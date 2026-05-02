import re

from researchpilot.schemas import DocumentChunk, PageText


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    cleaned = clean_text(text)
    if not cleaned:
        return []

    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0

    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(cleaned):
            break
        start += step

    return chunks


def chunk_pages(
    pages: list[PageText],
    paper_id: str,
    title: str | None = None,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []

    for page_item in pages:
        page_chunks = chunk_text(
            page_item.text,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        for idx, chunk in enumerate(page_chunks):
            chunk_id = f"{paper_id}_p{page_item.page}_{idx}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    paper_id=paper_id,
                    title=title,
                    page=page_item.page,
                    text=chunk,
                )
            )

    return chunks
