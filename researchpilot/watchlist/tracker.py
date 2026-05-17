from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

from researchpilot.cards.metadata_cards import metadata_paper_id
from researchpilot.discovery.semantic_scholar import search_semantic_scholar


DEFAULT_TRACKING_PATH = "data/outputs/watchlist_tracking.json"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"


def _normalize_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw = re.split(r"[\n,]+", values)
    elif isinstance(values, list):
        raw = [str(item) for item in values]
    else:
        raw = [str(values)]
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        value = str(item).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return cleaned


def watch_item_key(item: dict[str, Any]) -> str:
    identity = {
        "name": str(item.get("name", "")).strip().lower(),
        "type": str(item.get("type", "")).strip().lower(),
        "authors": [value.lower() for value in _normalize_list(item.get("authors", []))],
        "institutions": [value.lower() for value in _normalize_list(item.get("institutions", []))],
    }
    raw = json.dumps(identity, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def load_watchlist_tracking(path: str = DEFAULT_TRACKING_PATH) -> dict[str, dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def save_watchlist_tracking(
    tracking: dict[str, dict[str, Any]],
    path: str = DEFAULT_TRACKING_PATH,
) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        json.dumps(tracking, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_watch_item_tracking(
    item: dict[str, Any],
    path: str = DEFAULT_TRACKING_PATH,
) -> dict[str, Any] | None:
    tracking = load_watchlist_tracking(path)
    value = tracking.get(watch_item_key(item))
    return value if isinstance(value, dict) else None


def _extract_urls(*values: Any) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for value in values:
        for match in re.findall(r"https?://[^\s)>\]]+", str(value or "")):
            url = match.rstrip(".,;")
            key = url.lower()
            if key in seen:
                continue
            seen.add(key)
            urls.append(url)
    return urls


def homepage_index_for_watch_item(item: dict[str, Any]) -> list[dict[str, str]]:
    name = str(item.get("name", "")).strip()
    item_type = str(item.get("type", "custom") or "custom").strip()
    authors = _normalize_list(item.get("authors", []))
    institutions = _normalize_list(item.get("institutions", []))
    keywords = _normalize_list(item.get("keywords", []))
    homepage_urls = _normalize_list(item.get("homepage_urls", []))
    notes = str(item.get("notes", "") or "")

    query_parts = [name, *authors[:4], *institutions[:3], *keywords[:5]]
    query = " ".join(part for part in query_parts if part).strip() or name
    homepage_query = " ".join([query, "homepage research group lab publications"]).strip()
    scholar_query = " ".join([query, "recent papers"]).strip()

    rows: list[dict[str, str]] = []
    for url in [*homepage_urls, *_extract_urls(notes)]:
        rows.append({"label": "Explicit homepage/profile", "kind": "explicit", "url": url})

    rows.extend(
        [
            {
                "label": "Google homepage search",
                "kind": "homepage_search",
                "url": f"https://www.google.com/search?q={quote_plus(homepage_query)}",
            },
            {
                "label": "Google Scholar profile/papers",
                "kind": "scholar_search",
                "url": f"https://scholar.google.com/scholar?q={quote_plus(scholar_query)}",
            },
            {
                "label": "Semantic Scholar search",
                "kind": "semantic_scholar",
                "url": f"https://www.semanticscholar.org/search?q={quote_plus(query)}&sort=relevance",
            },
            {
                "label": "DBLP search",
                "kind": "dblp",
                "url": f"https://dblp.org/search?q={quote_plus(query)}",
            },
            {
                "label": "OpenAlex works search",
                "kind": "openalex",
                "url": f"https://openalex.org/works?filter=default.search:{quote_plus(query)}",
            },
        ]
    )
    if item_type in {"institution", "research_group"}:
        rows.append(
            {
                "label": "Institution/group publications search",
                "kind": "publication_index",
                "url": f"https://www.google.com/search?q={quote_plus(query + ' publications 2026 2025')}",
            }
        )
    return rows


def _http_json(url: str, timeout: int = 30) -> dict[str, Any]:
    mailto = os.getenv("OPENALEX_MAILTO") or os.getenv("RESEARCHPILOT_CONTACT_EMAIL")
    user_agent = "ResearchPilot/0.1"
    if mailto:
        user_agent = f"{user_agent} (mailto:{mailto})"
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _abstract_from_inverted_index(index: Any) -> str:
    if not isinstance(index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, offsets in index.items():
        if not isinstance(offsets, list):
            continue
        for offset in offsets:
            try:
                positions.append((int(offset), str(word)))
            except Exception:
                continue
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def _openalex_source(work: dict[str, Any]) -> dict[str, str]:
    location = work.get("primary_location")
    if not isinstance(location, dict):
        location = {}
    source = location.get("source")
    if not isinstance(source, dict):
        source = {}
    return {
        "display_name": str(source.get("display_name") or ""),
        "landing_page_url": str(location.get("landing_page_url") or work.get("doi") or work.get("id") or ""),
        "pdf_url": str(location.get("pdf_url") or ""),
    }


def _normalize_openalex_work(work: dict[str, Any]) -> dict[str, Any]:
    source = _openalex_source(work)
    authors: list[str] = []
    institutions: list[str] = []
    for authorship in work.get("authorships", []) or []:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author")
        if isinstance(author, dict) and author.get("display_name"):
            authors.append(str(author["display_name"]))
        for institution in authorship.get("institutions", []) or []:
            if isinstance(institution, dict) and institution.get("display_name"):
                institutions.append(str(institution["display_name"]))

    return {
        "source": "openalex",
        "source_url": source["landing_page_url"],
        "pdf_url": source["pdf_url"],
        "openalex_id": work.get("id") or "",
        "doi": work.get("doi") or "",
        "title": work.get("display_name") or work.get("title") or "",
        "authors": authors,
        "institutions": sorted(set(institutions)),
        "year": work.get("publication_year"),
        "publication_date": work.get("publication_date") or "",
        "venue": source["display_name"],
        "abstract": _abstract_from_inverted_index(work.get("abstract_inverted_index")),
        "cited_by_count": work.get("cited_by_count"),
        "collection_scope": "watchlist_tracking",
    }


def search_openalex_watch_papers(
    query: str,
    *,
    cutoff: date,
    limit: int,
) -> list[dict[str, Any]]:
    today = date.today()
    params = {
        "search": query,
        "filter": f"from_publication_date:{cutoff.isoformat()},to_publication_date:{today.isoformat()}",
        "sort": "publication_date:desc",
        "per-page": str(max(1, min(int(limit), 100))),
    }
    mailto = os.getenv("OPENALEX_MAILTO") or os.getenv("RESEARCHPILOT_CONTACT_EMAIL")
    if mailto:
        params["mailto"] = mailto
    payload = _http_json(f"{OPENALEX_WORKS_URL}?{urlencode(params)}")
    results = payload.get("results", [])
    if not isinstance(results, list):
        return []
    return [_normalize_openalex_work(item) for item in results if isinstance(item, dict)]


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except Exception:
        return None


def _is_recent(paper: dict[str, Any], cutoff: date) -> bool:
    parsed = _parse_date(paper.get("publication_date") or paper.get("published"))
    if parsed:
        return parsed >= cutoff
    try:
        return int(paper.get("year") or 0) >= cutoff.year
    except Exception:
        return False


def _contains_any(text: str, terms: list[str]) -> list[str]:
    lowered = str(text or "").lower()
    return [term for term in terms if term and term.lower() in lowered]


def _match_watch_item(paper: dict[str, Any], item: dict[str, Any]) -> list[str]:
    name = str(item.get("name", "")).strip()
    authors = _normalize_list(item.get("authors", []))
    institutions = _normalize_list(item.get("institutions", []))
    keywords = _normalize_list(item.get("keywords", []))
    paper_authors = " ".join(map(str, paper.get("authors", []) or []))
    paper_institutions = " ".join(map(str, paper.get("institutions", []) or []))
    text = " ".join(
        [
            str(paper.get("title", "")),
            str(paper.get("abstract", "")),
            str(paper.get("venue", "")),
            paper_authors,
            paper_institutions,
        ]
    )
    reasons: list[str] = []
    for author in _contains_any(paper_authors, authors):
        reasons.append(f"author:{author}")
    for institution in _contains_any(paper_institutions, [name, *institutions]):
        reasons.append(f"institution:{institution}")
    for keyword in _contains_any(text, keywords):
        reasons.append(f"keyword:{keyword}")
    if name and name.lower() in text.lower():
        reasons.append(f"name:{name}")
    if not reasons and not (authors or institutions or keywords):
        reasons.append("query_match")
    return sorted(set(reasons))


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(title or "").lower())


def _dedupe_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for paper in papers:
        key = str(paper.get("doi") or "").lower().strip() or metadata_paper_id(paper) or _title_key(str(paper.get("title", "")))
        if not key:
            continue
        current = best.get(key)
        if current is None:
            best[key] = paper
            continue
        current_score = int(current.get("cited_by_count") or 0)
        score = int(paper.get("cited_by_count") or 0)
        if paper.get("source") == "semantic_scholar" and current.get("source") != "semantic_scholar":
            best[key] = paper
        elif score > current_score:
            best[key] = paper
    return list(best.values())


def _watch_query(item: dict[str, Any]) -> str:
    parts = [
        str(item.get("name", "")).strip(),
        *_normalize_list(item.get("authors", []))[:5],
        *_normalize_list(item.get("institutions", []))[:3],
        *_normalize_list(item.get("keywords", []))[:8],
    ]
    return " ".join(part for part in parts if part).strip()


def track_watch_item(
    item: dict[str, Any],
    *,
    months: int = 6,
    max_results: int = 25,
    path: str = DEFAULT_TRACKING_PATH,
) -> dict[str, Any]:
    key = watch_item_key(item)
    tracking = load_watchlist_tracking(path)
    previous = tracking.get(key, {}) if isinstance(tracking.get(key), dict) else {}
    dismissed = previous.get("dismissed_paper_ids", [])
    if not isinstance(dismissed, list):
        dismissed = []

    months = max(1, int(months))
    max_results = max(1, min(int(max_results), 80))
    cutoff = date.today() - timedelta(days=30 * months)
    query = _watch_query(item)
    warnings: list[str] = []
    candidates: list[dict[str, Any]] = []

    if query:
        try:
            candidates.extend(
                search_semantic_scholar(
                    query=query,
                    limit=max_results,
                    year_from=cutoff.year,
                    year_to=date.today().year,
                )
            )
        except Exception as exc:
            warnings.append(f"Semantic Scholar tracking failed: {exc}")
        try:
            candidates.extend(search_openalex_watch_papers(query, cutoff=cutoff, limit=max_results))
        except Exception as exc:
            warnings.append(f"OpenAlex tracking failed: {exc}")

    papers: list[dict[str, Any]] = []
    for paper in _dedupe_papers(candidates):
        if not str(paper.get("title", "")).strip():
            continue
        if not _is_recent(paper, cutoff):
            continue
        reasons = _match_watch_item(paper, item)
        if not reasons:
            continue
        normalized = dict(paper)
        normalized["paper_id"] = metadata_paper_id(normalized)
        normalized["watch_match_reasons"] = reasons
        normalized["target_watch_item"] = str(item.get("name", ""))
        normalized["collection_scope"] = normalized.get("collection_scope") or "watchlist_tracking"
        papers.append(normalized)

    papers.sort(
        key=lambda paper: (
            str(paper.get("publication_date", "")),
            int(paper.get("year") or 0),
            int(paper.get("cited_by_count") or 0),
        ),
        reverse=True,
    )

    result = {
        "watch_key": key,
        "item": {
            "name": str(item.get("name", "")),
            "type": str(item.get("type", "")),
            "authors": _normalize_list(item.get("authors", [])),
            "institutions": _normalize_list(item.get("institutions", [])),
            "keywords": _normalize_list(item.get("keywords", [])),
            "homepage_urls": _normalize_list(item.get("homepage_urls", [])),
        },
        "tracked_at": datetime.now().isoformat(timespec="seconds"),
        "months": months,
        "cutoff_date": cutoff.isoformat(),
        "query": query,
        "homepage_index": homepage_index_for_watch_item(item),
        "papers": papers[:max_results],
        "paper_count": len(papers[:max_results]),
        "dismissed_paper_ids": dismissed,
        "warnings": warnings,
    }
    tracking[key] = result
    save_watchlist_tracking(tracking, path)
    return result


def dismiss_watch_paper(
    item: dict[str, Any],
    paper_id: str,
    *,
    path: str = DEFAULT_TRACKING_PATH,
) -> dict[str, Any]:
    tracking = load_watchlist_tracking(path)
    key = watch_item_key(item)
    row = tracking.get(key)
    if not isinstance(row, dict):
        row = {
            "watch_key": key,
            "item": {"name": str(item.get("name", "")), "type": str(item.get("type", ""))},
            "homepage_index": homepage_index_for_watch_item(item),
            "papers": [],
            "dismissed_paper_ids": [],
            "warnings": [],
        }
    dismissed = row.get("dismissed_paper_ids", [])
    if not isinstance(dismissed, list):
        dismissed = []
    paper_id = str(paper_id or "").strip()
    if paper_id and paper_id not in dismissed:
        dismissed.append(paper_id)
    row["dismissed_paper_ids"] = dismissed
    tracking[key] = row
    save_watchlist_tracking(tracking, path)
    return row
