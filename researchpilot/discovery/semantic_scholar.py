from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen


SEMANTIC_SCHOLAR_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
DEFAULT_FIELDS = ",".join(
    [
        "paperId",
        "title",
        "abstract",
        "year",
        "publicationDate",
        "authors",
        "venue",
        "url",
        "externalIds",
        "citationCount",
        "isOpenAccess",
        "openAccessPdf",
        "publicationTypes",
        "fieldsOfStudy",
    ]
)


def _api_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "ResearchPilot/0.1",
    }
    api_key = (
        os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        or os.getenv("S2_API_KEY")
        or os.getenv("S2_APIKEY")
        or ""
    ).strip()
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _http_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = Request(url, headers=_api_headers())
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _year_filter(year_from: int | None, year_to: int | None) -> str | None:
    if year_from and year_to:
        if year_from == year_to:
            return str(year_from)
        return f"{min(year_from, year_to)}-{max(year_from, year_to)}"
    if year_from:
        return f"{year_from}-"
    if year_to:
        return f"-{year_to}"
    return None


def _normalize_paper(paper: dict[str, Any]) -> dict[str, Any]:
    authors = []
    for author in paper.get("authors", []) or []:
        if isinstance(author, dict) and author.get("name"):
            authors.append(str(author["name"]))

    external_ids = paper.get("externalIds")
    if not isinstance(external_ids, dict):
        external_ids = {}
    open_access_pdf = paper.get("openAccessPdf")
    if not isinstance(open_access_pdf, dict):
        open_access_pdf = {}

    return {
        "semantic_scholar_paper_id": paper.get("paperId") or "",
        "source": "semantic_scholar",
        "source_url": paper.get("url") or "",
        "pdf_url": open_access_pdf.get("url") or "",
        "doi": external_ids.get("DOI") or external_ids.get("doi") or "",
        "arxiv_id": external_ids.get("ArXiv") or external_ids.get("arXiv") or "",
        "title": paper.get("title") or "",
        "authors": authors,
        "year": paper.get("year"),
        "publication_date": paper.get("publicationDate") or "",
        "venue": paper.get("venue") or "",
        "abstract": paper.get("abstract") or "",
        "cited_by_count": paper.get("citationCount"),
        "is_open_access": paper.get("isOpenAccess"),
        "publication_types": paper.get("publicationTypes") or [],
        "fields_of_study": paper.get("fieldsOfStudy") or [],
        "external_ids": external_ids,
    }


def search_semantic_scholar(
    query: str,
    *,
    limit: int = 20,
    year_from: int | None = None,
    year_to: int | None = None,
    fields: str = DEFAULT_FIELDS,
    timeout: int = 30,
) -> list[dict[str, Any]]:
    """Search Semantic Scholar Academic Graph and normalize paper metadata."""
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return []

    capped_limit = max(1, min(int(limit), 100))
    params: dict[str, str] = {
        "query": normalized_query,
        "limit": str(capped_limit),
        "fields": fields,
    }
    year = _year_filter(year_from, year_to)
    if year:
        params["year"] = year

    payload = _http_json(f"{SEMANTIC_SCHOLAR_SEARCH_URL}?{urlencode(params)}", timeout=timeout)
    data = payload.get("data", [])
    if not isinstance(data, list):
        return []
    return [_normalize_paper(item) for item in data if isinstance(item, dict)]
