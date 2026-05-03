from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

try:
    import arxiv
except ModuleNotFoundError:
    arxiv = None  # type: ignore[assignment]


def sanitize_filename(name: str, max_length: int = 120) -> str:
    if max_length <= 0:
        max_length = 120

    normalized = (name or "").strip().replace(" ", "_")
    normalized = re.sub(r"[^\w.\-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("._-")
    if len(normalized) > max_length:
        normalized = normalized[:max_length].rstrip("._-")

    return normalized or "paper"


def _to_iso_datetime(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _extract_arxiv_id(entry_id: str, fallback_short_id: str = "") -> str:
    if fallback_short_id:
        return fallback_short_id.split("v", 1)[0]
    if not entry_id:
        return ""

    marker = "/abs/"
    if marker in entry_id:
        return entry_id.split(marker, 1)[1].split("v", 1)[0]
    return entry_id.rstrip("/").split("/")[-1].split("v", 1)[0]


def search_arxiv_papers(
    query: str,
    max_results: int = 10,
    sort_by: str = "relevance",
) -> list[dict]:
    if arxiv is None:
        raise RuntimeError("arxiv package is not installed. Please install dependencies first.")

    if not query or not query.strip():
        return []

    if max_results <= 0:
        return []

    sort_mapping = {
        "relevance": arxiv.SortCriterion.Relevance,
        "submitted_date": arxiv.SortCriterion.SubmittedDate,
    }
    sort_criterion = sort_mapping.get(sort_by, arxiv.SortCriterion.Relevance)

    search = arxiv.Search(
        query=query.strip(),
        max_results=max_results,
        sort_by=sort_criterion,
    )

    page_size = min(max_results, 10)
    page_size = max(page_size, 1)
    client = arxiv.Client(
        delay_seconds=3.0,
        num_retries=3,
        page_size=page_size,
    )

    results: list[dict] = []
    try:
        for item in client.results(search):
            short_id = item.get_short_id() if hasattr(item, "get_short_id") else ""
            arxiv_id = _extract_arxiv_id(item.entry_id, fallback_short_id=short_id)
            results.append(
                {
                    "source": "arxiv",
                    "entry_id": item.entry_id,
                    "arxiv_id": arxiv_id,
                    "title": item.title,
                    "authors": [author.name for author in item.authors],
                    "summary": item.summary,
                    "published": _to_iso_datetime(item.published),
                    "updated": _to_iso_datetime(item.updated),
                    "pdf_url": item.pdf_url,
                    "primary_category": item.primary_category,
                    "categories": list(item.categories),
                }
            )
    except Exception as exc:
        msg = str(exc)
        if "429" in msg or "Too Many Requests" in msg:
            raise RuntimeError(
                "arXiv search failed due to rate limit (HTTP 429). Please wait and retry later."
            ) from exc
        raise RuntimeError(
            f"arXiv search failed. This may be due to arXiv rate limits or network issues: {msg}"
        ) from exc

    return results


def download_pdf_from_url(
    pdf_url: str,
    output_dir: str = "data/uploads",
    filename: str | None = None,
) -> str:
    if not pdf_url or not pdf_url.strip():
        raise ValueError("pdf_url is empty.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if filename is None:
        parsed = urlparse(pdf_url)
        basename = Path(parsed.path).name or "paper.pdf"
        filename = basename

    safe_name = sanitize_filename(filename)
    if not safe_name.lower().endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"

    local_path = output_path / safe_name

    try:
        with urlopen(pdf_url, timeout=60) as response:
            local_path.write_bytes(response.read())
    except Exception as exc:
        raise RuntimeError(f"Failed to download PDF from {pdf_url}: {exc}") from exc

    return str(local_path)


def download_arxiv_paper(
    paper: dict,
    output_dir: str = "data/uploads",
) -> str:
    pdf_url = str(paper.get("pdf_url", "")).strip()
    if not pdf_url:
        raise ValueError("paper does not contain a valid pdf_url.")

    arxiv_id = sanitize_filename(str(paper.get("arxiv_id", "")), max_length=40)
    title = sanitize_filename(str(paper.get("title", "")), max_length=80)
    filename = f"arxiv_{arxiv_id}_{title}.pdf"

    return download_pdf_from_url(
        pdf_url=pdf_url,
        output_dir=output_dir,
        filename=filename,
    )
