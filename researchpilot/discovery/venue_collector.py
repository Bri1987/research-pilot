from __future__ import annotations

import os
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

from researchpilot.cards.metadata_cards import normalize_doi
from researchpilot.discovery.ccf_venues import CCF_DIRECTORY_SOURCE_URL
from researchpilot.discovery.ccf_venues import CCF_SOURCE_VERSION
from researchpilot.discovery.ccf_venues import DOMAIN_KEYWORDS
from researchpilot.discovery.ccf_venues import VenueSeed
from researchpilot.discovery.ccf_venues import build_topic_keywords
from researchpilot.discovery.ccf_venues import infer_domains
from researchpilot.discovery.ccf_venues import scholar_followup_urls
from researchpilot.discovery.ccf_venues import select_venues
from researchpilot.discovery.semantic_scholar import search_semantic_scholar
from researchpilot.search.arxiv_search import search_arxiv_papers


OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENREVIEW_NOTES_URL = "https://api2.openreview.net/notes"


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", str(text or "").lower())


def _http_json(url: str, timeout: int = 30) -> dict[str, Any]:
    mailto = os.getenv("OPENALEX_MAILTO") or os.getenv("RESEARCHPILOT_CONTACT_EMAIL")
    user_agent = "ResearchPilot/0.1"
    if mailto:
        user_agent = f"{user_agent} (mailto:{mailto})"
    req = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        import json

        return json.loads(response.read().decode("utf-8"))


def _content_value(content: dict[str, Any], key: str) -> Any:
    value = content.get(key)
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


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


def _paper_relevance(paper: dict[str, Any], keywords: list[str], venue: VenueSeed | None = None) -> tuple[float, list[str]]:
    keyword_terms = [_tokenize(keyword) for keyword in keywords]
    flat_keywords = [" ".join(tokens) for tokens in keyword_terms if tokens]
    text_parts = [
        str(paper.get("title", "")),
        str(paper.get("abstract", "")),
        str(paper.get("venue", "")),
    ]
    text = " ".join(text_parts).lower()
    title = str(paper.get("title", "")).lower()
    text_tokens = set(_tokenize(text))

    score = 0.0
    matched: list[str] = []
    for keyword, tokens in zip(flat_keywords, keyword_terms):
        if not keyword:
            continue
        if keyword in title:
            score += 4.0
            matched.append(keyword)
        elif keyword in text:
            score += 1.5
            matched.append(keyword)
        else:
            if len(tokens) <= 1:
                token = tokens[0] if tokens else ""
                if len(token) >= 3 and token in text_tokens:
                    score += 0.5
                    matched.append(keyword)
                continue
            required = len(tokens) if len(tokens) <= 5 else max(2, int(len(tokens) * 0.8))
            if sum(1 for token in tokens if token in text_tokens) >= required:
                score += 0.75
                matched.append(keyword)

    if venue is not None:
        venue_terms = [venue.acronym, venue.name, *venue.aliases, *venue.openalex_terms]
        if any(str(term).lower() in text for term in venue_terms if term):
            score += 3.0
            matched.append(venue.acronym)

    return score, sorted(set(matched))


def _keyword_matches_text(keyword: str, text: str, text_tokens: set[str]) -> bool:
    normalized = str(keyword or "").lower().strip()
    if not normalized:
        return False
    if not re.search(r"[A-Za-z0-9]", normalized):
        return normalized in text
    phrase_parts = [re.escape(part) for part in re.split(r"\s+", normalized) if part]
    if phrase_parts:
        phrase = r"\s+".join(phrase_parts)
        pattern = rf"(?<![A-Za-z0-9_\u4e00-\u9fff]){phrase}(?![A-Za-z0-9_\u4e00-\u9fff])"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True
    tokens = _tokenize(normalized)
    if not tokens:
        return False
    if len(tokens) == 1:
        return len(tokens[0]) >= 3 and tokens[0] in text_tokens
    if len(tokens) > 1:
        required = len(tokens) if len(tokens) <= 5 else max(2, int(len(tokens) * 0.8))
        return sum(1 for token in tokens if token in text_tokens) >= required
    return False


def _paper_domain_matches(paper: dict[str, Any], domains: list[str]) -> list[str]:
    text = " ".join(
        [
            str(paper.get("title", "")),
            str(paper.get("abstract", "")),
            str(paper.get("venue", "")),
        ]
    ).lower()
    text_tokens = set(_tokenize(text))
    matches: list[str] = []
    for domain in domains:
        keywords = DOMAIN_KEYWORDS.get(domain, ())
        if any(_keyword_matches_text(keyword, text, text_tokens) for keyword in keywords):
            matches.append(domain)
    return sorted(set(matches))


def _compact_paper(paper: dict[str, Any], abstract_limit: int = 900) -> dict[str, Any]:
    abstract = str(paper.get("abstract", "") or "").replace("\n", " ").strip()
    compact = dict(paper)
    compact["abstract"] = abstract[:abstract_limit]
    compact["abstract_truncated"] = len(abstract) > abstract_limit
    return compact


def plan_venue_collection(
    topic: str,
    domains: list[str] | None = None,
    keywords: list[str] | None = None,
    venues: list[str] | None = None,
    include_journals: bool = True,
    max_venues: int = 12,
) -> dict[str, Any]:
    inferred_domains = infer_domains(topic, domains)
    topic_keywords = build_topic_keywords(topic, inferred_domains, keywords)
    selected = select_venues(
        topic=topic,
        domains=inferred_domains,
        requested_venues=venues,
        include_journals=include_journals,
        max_venues=max_venues,
    )
    return {
        "topic": topic,
        "domains": inferred_domains,
        "keywords": topic_keywords,
        "ccf_source": {
            "version": CCF_SOURCE_VERSION,
            "url": CCF_DIRECTORY_SOURCE_URL,
            "note": (
                "The local seed is intentionally compact. Treat ccf_rank as a planning hint "
                "and verify exact ranking on the official CCF directory for high-stakes use."
            ),
        },
        "venues": [venue.to_dict() for venue in selected],
        "source_plan": [
            {
                "venue": venue.acronym,
                "official_or_proceedings_url": venue.proceedings_url or venue.homepage,
                "openreview_id_template": venue.openreview_id_template,
                "openalex_terms": list(venue.openalex_terms),
            }
            for venue in selected
        ],
        "scholar_followup_urls": scholar_followup_urls(topic, topic_keywords, selected),
    }


def _openreview_years_for_venue(venue: VenueSeed, years: list[int]) -> list[tuple[int, str]]:
    if not venue.openreview_id_template:
        return []
    pairs: list[tuple[int, str]] = []
    for year in years:
        pairs.append((year, venue.openreview_id_template.format(year=year)))
    return pairs


def collect_openreview_for_venue(
    venue: VenueSeed,
    years: list[int],
    keywords: list[str],
    limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    papers: list[dict[str, Any]] = []
    warnings: list[str] = []
    for year, venue_id in _openreview_years_for_venue(venue, years):
        params = urlencode({"content.venueid": venue_id, "limit": max(1, min(limit, 100))})
        url = f"{OPENREVIEW_NOTES_URL}?{params}"
        try:
            payload = _http_json(url)
        except Exception as exc:
            warnings.append(f"OpenReview failed for {venue.acronym} {year}: {exc}")
            continue

        notes = payload.get("notes", [])
        if not isinstance(notes, list):
            continue
        for note in notes[:limit]:
            if not isinstance(note, dict):
                continue
            content = note.get("content", {})
            if not isinstance(content, dict):
                content = {}
            note_id = str(note.get("id", "") or "")
            title = str(_content_value(content, "title") or "").strip()
            if not title:
                continue
            authors = _content_value(content, "authors")
            if not isinstance(authors, list):
                authors = []
            abstract = str(_content_value(content, "abstract") or "").strip()
            paper = {
                "source": "openreview",
                "source_url": f"https://openreview.net/forum?id={note_id}" if note_id else "",
                "pdf_url": f"https://openreview.net/pdf?id={note_id}" if note_id else "",
                "title": title,
                "authors": [str(author) for author in authors],
                "year": year,
                "publication_date": str(note.get("pdate") or note.get("cdate") or ""),
                "venue": venue.acronym,
                "venue_full_name": venue.name,
                "venue_id": venue_id,
                "venue_rank": venue.ccf_rank,
                "venue_field": venue.ccf_field,
                "target_venue": venue.acronym,
                "target_venue_full_name": venue.name,
                "target_venue_rank": venue.ccf_rank,
                "target_venue_field": venue.ccf_field,
                "matched_selected_venue": True,
                "collection_scope": "venue",
                "abstract": abstract,
                "doi": "",
                "cited_by_count": None,
            }
            score, matched = _paper_relevance(paper, keywords, venue)
            paper["relevance_score"] = score
            paper["matched_keywords"] = matched
            papers.append(paper)
        time.sleep(0.1)
    return papers, warnings


def _openalex_query(topic: str, venue: VenueSeed, keywords: list[str], year_from: int, year_to: int, limit: int) -> str:
    terms = [topic, venue.acronym, *(venue.openalex_terms[:2]), *(keywords[:4])]
    search = " ".join(str(term).strip() for term in terms if str(term).strip())
    filters = f"from_publication_date:{year_from}-01-01,to_publication_date:{year_to}-12-31"
    params = {
        "search": search,
        "filter": filters,
        "sort": "publication_date:desc",
        "per-page": str(max(1, min(limit, 200))),
    }
    mailto = os.getenv("OPENALEX_MAILTO") or os.getenv("RESEARCHPILOT_CONTACT_EMAIL")
    if mailto:
        params["mailto"] = mailto
    return f"{OPENALEX_WORKS_URL}?{urlencode(params)}"


def _openalex_source(work: dict[str, Any]) -> dict[str, Any]:
    location = work.get("primary_location")
    if not isinstance(location, dict):
        location = {}
    source = location.get("source")
    if not isinstance(source, dict):
        source = {}
    return {
        "display_name": source.get("display_name") or "",
        "type": source.get("type") or "",
        "landing_page_url": location.get("landing_page_url") or work.get("doi") or work.get("id") or "",
        "pdf_url": location.get("pdf_url") or "",
    }


def _source_matches_venue(source_name: str, venue: VenueSeed) -> bool:
    text = str(source_name or "").lower()
    if not text:
        return False
    terms = [venue.acronym, venue.name, *venue.aliases, *venue.openalex_terms]
    return any(str(term).lower() in text for term in terms if len(str(term).strip()) > 2)


def collect_openalex_for_venue(
    topic: str,
    venue: VenueSeed,
    years: list[int],
    keywords: list[str],
    limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    year_from = min(years)
    year_to = max(years)
    url = _openalex_query(topic, venue, keywords, year_from, year_to, limit)
    warnings: list[str] = []
    try:
        payload = _http_json(url)
    except Exception as exc:
        return [], [f"OpenAlex failed for {venue.acronym}: {exc}"]

    results = payload.get("results", [])
    if not isinstance(results, list):
        return [], warnings

    papers: list[dict[str, Any]] = []
    for work in results:
        if not isinstance(work, dict):
            continue
        source = _openalex_source(work)
        authors: list[str] = []
        for authorship in work.get("authorships", []) or []:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author")
            if isinstance(author, dict) and author.get("display_name"):
                authors.append(str(author["display_name"]))

        matched_selected_venue = _source_matches_venue(source["display_name"], venue)
        paper = {
            "source": "openalex",
            "source_url": source["landing_page_url"],
            "pdf_url": source["pdf_url"],
            "openalex_id": work.get("id") or "",
            "doi": work.get("doi") or "",
            "title": work.get("display_name") or work.get("title") or "",
            "authors": authors,
            "year": work.get("publication_year"),
            "publication_date": work.get("publication_date") or "",
            "venue": source["display_name"] or venue.acronym,
            "venue_full_name": source["display_name"] or "",
            "venue_rank": venue.ccf_rank if matched_selected_venue else "",
            "venue_field": venue.ccf_field if matched_selected_venue else "",
            "target_venue": venue.acronym,
            "target_venue_full_name": venue.name,
            "target_venue_rank": venue.ccf_rank,
            "target_venue_field": venue.ccf_field,
            "matched_selected_venue": matched_selected_venue,
            "collection_scope": "venue" if matched_selected_venue else "broad_openalex",
            "abstract": _abstract_from_inverted_index(work.get("abstract_inverted_index")),
            "cited_by_count": work.get("cited_by_count"),
        }
        if not str(paper["title"]).strip():
            continue
        score, matched = _paper_relevance(paper, keywords, venue)
        paper["relevance_score"] = score
        paper["matched_keywords"] = matched
        papers.append(paper)
    return papers, warnings


def collect_semantic_scholar_for_topic(
    topic: str,
    keywords: list[str],
    domains: list[str],
    years: list[int],
    limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    year_from = min(years) if years else None
    year_to = max(years) if years else None
    query_terms = [topic, *keywords[:8]]
    query = " ".join(str(term).strip() for term in query_terms if str(term).strip())
    warnings: list[str] = []
    try:
        results = search_semantic_scholar(
            query=query,
            limit=limit,
            year_from=year_from,
            year_to=year_to,
        )
    except Exception as exc:
        return [], [f"Semantic Scholar failed for topic query: {exc}"]

    papers: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict) or not str(item.get("title", "")).strip():
            continue
        paper = {
            **item,
            "venue_full_name": item.get("venue", ""),
            "venue_rank": "",
            "venue_field": "",
            "target_venue": "Semantic Scholar broad search",
            "target_venue_full_name": "Semantic Scholar Academic Graph topic search",
            "target_venue_rank": "",
            "target_venue_field": "",
            "matched_selected_venue": False,
            "collection_scope": "broad_semantic_scholar",
        }
        score, matched = _paper_relevance(paper, keywords, venue=None)
        paper["relevance_score"] = score
        paper["matched_keywords"] = matched
        paper["domain_matches"] = _paper_domain_matches(paper, domains)
        papers.append(paper)
    return papers, warnings


def _year_from_date(value: Any) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", str(value or ""))
    if not match:
        return None
    try:
        return int(match.group(0))
    except Exception:
        return None


def collect_arxiv_for_topic(
    topic: str,
    keywords: list[str],
    domains: list[str],
    years: list[int],
    limit: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    query_terms = [topic, *keywords[:8]]
    query = " ".join(str(term).strip() for term in query_terms if str(term).strip())
    warnings: list[str] = []
    try:
        results = search_arxiv_papers(
            query=query,
            max_results=limit,
            sort_by="submitted_date",
        )
    except Exception as exc:
        return [], [f"arXiv failed for topic query: {exc}"]

    year_set = {int(year) for year in years} if years else set()
    papers: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict) or not str(item.get("title", "")).strip():
            continue
        year = _year_from_date(item.get("published") or item.get("updated"))
        if year_set and year not in year_set:
            continue
        paper = {
            "source": "arxiv",
            "source_url": item.get("entry_id", ""),
            "pdf_url": item.get("pdf_url", ""),
            "arxiv_id": item.get("arxiv_id", ""),
            "title": item.get("title", ""),
            "authors": item.get("authors", []),
            "year": year,
            "publication_date": item.get("published", ""),
            "venue": "arXiv",
            "venue_full_name": "arXiv",
            "venue_rank": "",
            "venue_field": "",
            "target_venue": "arXiv broad search",
            "target_venue_full_name": "arXiv topic search",
            "target_venue_rank": "",
            "target_venue_field": "",
            "matched_selected_venue": False,
            "collection_scope": "arxiv",
            "abstract": item.get("summary", ""),
            "summary": item.get("summary", ""),
            "primary_category": item.get("primary_category", ""),
            "categories": item.get("categories", []),
            "doi": "",
            "cited_by_count": None,
        }
        score, matched = _paper_relevance(paper, keywords, venue=None)
        paper["relevance_score"] = score
        paper["matched_keywords"] = matched
        paper["domain_matches"] = _paper_domain_matches(paper, domains)
        papers.append(paper)
    return papers, warnings


def _title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(title or "").lower())


def _doi_key(value: Any) -> str:
    return normalize_doi(value)


def _prefer_paper(current: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    current_score = float(current.get("relevance_score", 0.0) or 0.0)
    candidate_score = float(candidate.get("relevance_score", 0.0) or 0.0)
    if candidate.get("source") == "openreview" and current.get("source") != "openreview":
        return candidate
    if candidate_score > current_score:
        return candidate
    if (
        candidate_score == current_score
        and _doi_key(candidate.get("doi"))
        and not _doi_key(current.get("doi"))
    ):
        return candidate
    return current


def _matching_dedupe_group(
    doi: str,
    title: str,
    groups: list[dict[str, Any]],
    doi_index: dict[str, int],
    title_index: dict[str, set[int]],
) -> int | None:
    if doi and doi in doi_index:
        return doi_index[doi]
    if not title:
        return None

    title_matches = title_index.get(title, set())
    if not title_matches:
        return None

    if not doi:
        return next(iter(title_matches)) if len(title_matches) == 1 else None

    no_doi_matches = [idx for idx in title_matches if not groups[idx]["dois"]]
    if len(title_matches) == 1 and no_doi_matches:
        return no_doi_matches[0]
    return None


def deduplicate_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    doi_index: dict[str, int] = {}
    title_index: dict[str, set[int]] = {}

    for paper in papers:
        doi = _doi_key(paper.get("doi"))
        title = _title_key(str(paper.get("title", "")))
        if not doi and not title:
            continue

        match_idx = _matching_dedupe_group(doi, title, groups, doi_index, title_index)
        if match_idx is None:
            match_idx = len(groups)
            groups.append({"paper": paper, "dois": set(), "titles": set()})
        else:
            groups[match_idx]["paper"] = _prefer_paper(groups[match_idx]["paper"], paper)

        if doi:
            groups[match_idx]["dois"].add(doi)
            doi_index[doi] = match_idx
        if title:
            groups[match_idx]["titles"].add(title)
            title_index.setdefault(title, set()).add(match_idx)

    return [group["paper"] for group in groups]


def collect_venue_papers(
    topic: str,
    domains: list[str] | None = None,
    keywords: list[str] | None = None,
    venues: list[str] | None = None,
    years: list[int] | None = None,
    include_journals: bool = True,
    max_venues: int = 10,
    max_results_per_venue: int = 8,
    max_total: int = 60,
    include_arxiv: bool = True,
    include_openreview: bool = True,
    include_openalex: bool = True,
    include_broad_openalex: bool = True,
    include_semantic_scholar: bool = False,
    include_broad_semantic_scholar: bool = True,
    min_relevance_score: float = 1.0,
) -> dict[str, Any]:
    current_year = datetime.now().year
    years = years or [current_year, current_year - 1, current_year - 2]
    years = sorted({int(year) for year in years}, reverse=True)
    plan = plan_venue_collection(
        topic=topic,
        domains=domains,
        keywords=keywords,
        venues=venues,
        include_journals=include_journals,
        max_venues=max_venues,
    )
    selected = [
        VenueSeed(
            acronym=item["acronym"],
            name=item["name"],
            ccf_rank=item["ccf_rank"],
            ccf_field=item["ccf_field"],
            kind=item["kind"],
            domains=tuple(item["domains"]),
            aliases=tuple(item.get("aliases", [])),
            homepage=item.get("homepage", ""),
            proceedings_url=item.get("proceedings_url", ""),
            ccf_source_url=item.get("ccf_source_url", CCF_DIRECTORY_SOURCE_URL),
            openreview_id_template=item.get("openreview_id_template"),
            openalex_terms=tuple(item.get("openalex_terms", [])),
        )
        for item in plan["venues"]
    ]

    all_papers: list[dict[str, Any]] = []
    warnings: list[str] = []
    plan_domains = [str(domain) for domain in plan.get("domains", []) if str(domain)]
    if include_arxiv:
        papers, source_warnings = collect_arxiv_for_topic(
            topic=topic,
            keywords=plan["keywords"],
            domains=plan_domains,
            years=years,
            limit=max(1, min(max_total, max_results_per_venue * 2)),
        )
        all_papers.extend(papers)
        warnings.extend(source_warnings)

    for venue in selected:
        if include_openreview and venue.openreview_id_template:
            papers, venue_warnings = collect_openreview_for_venue(
                venue=venue,
                years=years,
                keywords=plan["keywords"],
                limit=max_results_per_venue,
            )
            all_papers.extend(papers)
            warnings.extend(venue_warnings)
        if include_openalex:
            papers, venue_warnings = collect_openalex_for_venue(
                topic=topic,
                venue=venue,
                years=years,
                keywords=plan["keywords"],
                limit=max_results_per_venue,
            )
            all_papers.extend(papers)
            warnings.extend(venue_warnings)
        time.sleep(0.1)

    if include_semantic_scholar:
        papers, source_warnings = collect_semantic_scholar_for_topic(
            topic=topic,
            keywords=plan["keywords"],
            domains=plan_domains,
            years=years,
            limit=max_total,
        )
        all_papers.extend(papers)
        warnings.extend(source_warnings)

    deduped = deduplicate_papers(all_papers)
    for paper in deduped:
        if isinstance(paper, dict):
            paper["domain_matches"] = _paper_domain_matches(paper, plan_domains)
    filtered = [
        paper
        for paper in deduped
        if float(paper.get("relevance_score", 0.0) or 0.0) >= min_relevance_score
        and (include_broad_openalex or paper.get("collection_scope") != "broad_openalex")
        and (include_broad_semantic_scholar or paper.get("collection_scope") != "broad_semantic_scholar")
    ]
    filtered.sort(
        key=lambda paper: (
            -float(paper.get("relevance_score", 0.0) or 0.0),
            -(int(paper.get("year") or 0)),
            str(paper.get("title", "")),
        )
    )
    filtered = filtered[:max_total]

    return {
        "topic": topic,
        "collected_at": datetime.now().isoformat(timespec="seconds"),
        "years": years,
        "plan": plan,
        "paper_count": len(filtered),
        "source_config": {
            "arxiv": include_arxiv,
            "openreview": include_openreview,
            "openalex": include_openalex,
            "semantic_scholar": include_semantic_scholar,
            "include_journals": include_journals,
        },
        "papers": [_compact_paper(paper) for paper in filtered],
        "warnings": warnings,
        "next_step": (
            "Use prepare_venue_paper_summary for agent-native synthesis, or ingest selected PDFs "
            "when pdf_url is available and paper-level RAG is needed."
        ),
    }
