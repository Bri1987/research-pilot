from __future__ import annotations

import json
import os
import re
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "data" / "agent_state"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs" / "agent"
CHUNKS_PATH = STATE_DIR / "chunks.json"
LAST_ARXIV_RESULTS_PATH = STATE_DIR / "last_arxiv_results.json"
LAST_VENUE_COLLECTION_PATH = STATE_DIR / "last_venue_collection.json"
PAPER_CARD_CACHE_PATH = PROJECT_ROOT / "data" / "outputs" / "paper_cards_cache.json"
AGENT_CARD_FIELDS = [
    "paper_id",
    "title",
    "problem",
    "method",
    "contribution",
    "dataset",
    "result",
    "limitation",
    "future_work",
    "relevance",
]


class AgentToolError(RuntimeError):
    pass


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return str(value)


def _read_json_stdin() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise AgentToolError("Tool input must be a JSON object.")
    return data


def _write_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _as_int(value: Any, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        number = int(value)
    except Exception:
        number = int(default)
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = re.split(r"[\n,]+", value)
        return [part.strip() for part in parts if part.strip()]
    return [str(value).strip()] if str(value).strip() else []


def _resolve_project_path(value: str | None, *, must_exist: bool = False) -> Path:
    if not value or not str(value).strip():
        raise AgentToolError("Path argument is empty.")

    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if must_exist and not path.exists():
        raise AgentToolError(f"Path does not exist: {path}")
    return path


def _safe_artifact_name(prefix: str, suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prefix = re.sub(r"[^A-Za-z0-9_.-]+", "_", prefix).strip("._-") or "artifact"
    return OUTPUT_DIR / f"{safe_prefix}_{stamp}{suffix}"


def _write_text_artifact(prefix: str, text: str, suffix: str = ".md") -> str:
    path = _safe_artifact_name(prefix, suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    latest_path = path.parent / f"latest_{re.sub(r'[^A-Za-z0-9_.-]+', '_', prefix).strip('._-')}{suffix}"
    latest_path.write_text(text, encoding="utf-8")
    return str(path)


def _read_text_arg(args: dict[str, Any], text_key: str, path_key: str) -> str:
    text = str(args.get(text_key, "") or "")
    if text.strip():
        return text

    raw_path = args.get(path_key)
    if raw_path:
        path = _resolve_project_path(str(raw_path), must_exist=True)
        return path.read_text(encoding="utf-8")

    raise AgentToolError(f"Provide either {text_key} or {path_key}.")


def _parse_json_object_arg(args: dict[str, Any], object_key: str, json_key: str) -> dict[str, Any]:
    value = args.get(object_key)
    if isinstance(value, dict):
        return dict(value)

    raw_json = args.get(json_key)
    if raw_json:
        parsed = json.loads(str(raw_json))
        if isinstance(parsed, dict):
            return parsed

    raise AgentToolError(f"Provide either {object_key} object or {json_key} JSON object string.")


def _parse_json_list_arg(args: dict[str, Any], list_key: str, json_key: str) -> list[dict[str, Any]]:
    value = args.get(list_key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]

    raw_json = args.get(json_key)
    if raw_json:
        parsed = json.loads(str(raw_json))
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]

    raise AgentToolError(f"Provide either {list_key} list or {json_key} JSON list string.")


def _parse_int_list_arg(value: Any) -> list[int]:
    raw_items = _as_list(value)
    years: list[int] = []
    for raw in raw_items:
        try:
            year = int(raw)
        except Exception:
            continue
        if 1900 <= year <= 2100 and year not in years:
            years.append(year)
    return years


def _chunk_to_dict(chunk: Any) -> dict[str, Any]:
    if isinstance(chunk, dict):
        data = dict(chunk)
    elif hasattr(chunk, "model_dump"):
        data = chunk.model_dump()
    elif hasattr(chunk, "dict"):
        data = chunk.dict()
    else:
        data = {
            "chunk_id": getattr(chunk, "chunk_id", ""),
            "paper_id": getattr(chunk, "paper_id", ""),
            "title": getattr(chunk, "title", None),
            "page": getattr(chunk, "page", 0),
            "text": getattr(chunk, "text", ""),
        }

    return {
        "chunk_id": str(data.get("chunk_id", "")),
        "paper_id": str(data.get("paper_id", "")),
        "title": data.get("title"),
        "page": int(data.get("page", 0) or 0),
        "text": str(data.get("text", "") or ""),
    }


def _load_chunk_dicts() -> list[dict[str, Any]]:
    data = _load_json(CHUNKS_PATH, [])
    if not isinstance(data, list):
        return []

    chunks: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized = _chunk_to_dict(item)
        if normalized["chunk_id"] and normalized["paper_id"] and normalized["text"].strip():
            chunks.append(normalized)
    return chunks


def _save_chunk_dicts(chunks: list[dict[str, Any]]) -> None:
    _save_json(CHUNKS_PATH, chunks)


def _dicts_to_chunks(chunk_dicts: list[dict[str, Any]]) -> list[Any]:
    try:
        from researchpilot.schemas import DocumentChunk
    except Exception as exc:
        raise AgentToolError(f"Cannot import ResearchPilot schemas. Install dependencies first: {exc}") from exc

    return [DocumentChunk(**_chunk_to_dict(item)) for item in chunk_dicts]


def _replace_paper_chunks(paper_id: str, new_chunks: list[Any]) -> dict[str, Any]:
    paper_key = str(paper_id or "").strip()
    if not paper_key:
        raise AgentToolError("paper_id is empty.")

    current = _load_chunk_dicts()
    removed = [item for item in current if item.get("paper_id") == paper_key]
    kept = [item for item in current if item.get("paper_id") != paper_key]
    normalized_new = [_chunk_to_dict(chunk) for chunk in new_chunks]
    _save_chunk_dicts(kept + normalized_new)

    if removed:
        try:
            from researchpilot.storage.corpus_store import delete_cached_paper_card

            delete_cached_paper_card(paper_key)
        except Exception:
            pass

    return {
        "paper_id": paper_key,
        "replaced_existing": bool(removed),
        "removed_chunks": len(removed),
        "new_chunks": len(normalized_new),
        "total_chunks": len(kept) + len(normalized_new),
    }


def _paper_summaries(chunk_dicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunk_dicts:
        grouped.setdefault(str(chunk.get("paper_id", "")), []).append(chunk)

    papers: list[dict[str, Any]] = []
    for paper_id, chunks in sorted(grouped.items()):
        pages = sorted({int(item.get("page", 0) or 0) for item in chunks if int(item.get("page", 0) or 0) > 0})
        titles = [str(item.get("title", "") or "").strip() for item in chunks if str(item.get("title", "") or "").strip()]
        title = titles[0] if titles else paper_id
        text_chars = sum(len(str(item.get("text", ""))) for item in chunks)
        papers.append(
            {
                "paper_id": paper_id,
                "title": title,
                "chunk_count": len(chunks),
                "page_count": len(pages),
                "first_page": pages[0] if pages else None,
                "last_page": pages[-1] if pages else None,
                "text_chars": text_chars,
            }
        )
    return papers


class BM25AgentRetriever:
    def __init__(self, chunks: list[Any]):
        self.chunks = list(chunks)
        self._fallback_index: list[dict[str, Any]] = []
        try:
            from researchpilot.retrieval.bm25_index import BM25Index

            self._index = BM25Index()
            self._index.build(self.chunks)
        except Exception:
            self._index = None
            self._build_fallback_index()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", str(text).lower())

    def _build_fallback_index(self) -> None:
        document_count = max(1, len(self.chunks))
        doc_freq: Counter[str] = Counter()
        rows: list[dict[str, Any]] = []

        for chunk in self.chunks:
            tokens = self._tokenize(chunk.text)
            counts = Counter(tokens)
            for token in counts:
                doc_freq[token] += 1
            rows.append(
                {
                    "chunk": chunk,
                    "counts": counts,
                    "length": max(1, len(tokens)),
                }
            )

        for row in rows:
            idf: dict[str, float] = {}
            for token in row["counts"]:
                idf[token] = 1.0 + max(0.0, (document_count - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5))
            row["idf"] = idf

        self._fallback_index = rows

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if self._index is not None:
            return self._index.search(query, top_k=top_k)

        query_tokens = self._tokenize(query)
        if not query_tokens or top_k <= 0:
            return []

        query_counts = Counter(query_tokens)
        scored: list[tuple[float, Any]] = []
        for row in self._fallback_index:
            counts: Counter[str] = row["counts"]
            length = float(row["length"])
            score = 0.0
            for token, query_weight in query_counts.items():
                tf = counts.get(token, 0)
                if tf <= 0:
                    continue
                score += float(query_weight) * (tf / length) * float(row["idf"].get(token, 1.0))
            if score > 0:
                scored.append((score, row["chunk"]))

        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[dict[str, Any]] = []
        for rank, (score, chunk) in enumerate(scored[:top_k], start=1):
            results.append(
                {
                    "rank": rank,
                    "score": float(score),
                    "chunk_id": chunk.chunk_id,
                    "paper_id": chunk.paper_id,
                    "page": chunk.page,
                    "text": chunk.text,
                }
            )
        return results

    def list_papers(self) -> list[str]:
        return sorted({chunk.paper_id for chunk in self.chunks})

    def get_chunks_by_paper(self, paper_id: str) -> list[Any]:
        return [chunk for chunk in self.chunks if chunk.paper_id == paper_id]


def _build_retriever(mode: str = "bm25") -> Any:
    chunks = _dicts_to_chunks(_load_chunk_dicts())
    if not chunks:
        raise AgentToolError("No papers are ingested. Run ingest_pdf or ingest_text first.")

    normalized_mode = str(mode or "bm25").strip().lower()
    if normalized_mode == "hybrid":
        try:
            from researchpilot.retrieval.hybrid_retriever import HybridRetriever
        except Exception as exc:
            raise AgentToolError(f"Cannot import hybrid retriever dependencies: {exc}") from exc

        retriever = HybridRetriever()
        retriever.build(chunks)
        retriever.chunks = list(chunks)
        return retriever

    return BM25AgentRetriever(chunks)


def _normalize_evidence(items: list[dict[str, Any]], text_limit: int | None = None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        text = str(item.get("text", "") or "")
        row = {
            "rank": item.get("rank"),
            "score": float(item.get("score", 0.0) or 0.0),
            "bm25_score": item.get("bm25_score"),
            "vector_score": item.get("vector_score"),
            "chunk_id": str(item.get("chunk_id", "") or ""),
            "paper_id": str(item.get("paper_id", "") or ""),
            "page": item.get("page"),
            "text": text if text_limit is None else text[:text_limit],
        }
        if text_limit is not None and len(text) > text_limit:
            row["truncated"] = True
        normalized.append(row)
    return normalized


def _load_dotenv_values() -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _llm_env_summary() -> dict[str, Any]:
    dotenv_values = _load_dotenv_values()

    def get_value(key: str) -> str:
        return os.getenv(key, dotenv_values.get(key, ""))

    return {
        "openai_api_key_configured": bool(get_value("OPENAI_API_KEY").strip()),
        "openai_base_url": get_value("OPENAI_BASE_URL") or None,
        "openai_model": get_value("OPENAI_MODEL") or None,
        "zen_minimax_hint": {
            "OPENAI_BASE_URL": "https://opencode.ai/zen/v1",
            "OPENAI_MODEL": "minimax-m2.5-free",
        },
    }


def cmd_status(args: dict[str, Any]) -> dict[str, Any]:
    chunk_dicts = _load_chunk_dicts()
    card_cache = _load_json(PAPER_CARD_CACHE_PATH, {})
    if not isinstance(card_cache, dict):
        card_cache = {}

    try:
        from researchpilot.watchlist.watchlist_store import load_watchlist

        watchlist = load_watchlist()
    except Exception:
        watchlist = []

    return {
        "project_root": str(PROJECT_ROOT),
        "state_dir": str(STATE_DIR),
        "output_dir": str(OUTPUT_DIR),
        "chunk_count": len(chunk_dicts),
        "papers": _paper_summaries(chunk_dicts),
        "paper_card_cache_count": len(card_cache),
        "watchlist_count": len(watchlist),
        "last_arxiv_results_saved": LAST_ARXIV_RESULTS_PATH.exists(),
        "last_venue_collection_saved": LAST_VENUE_COLLECTION_PATH.exists(),
        "llm": _llm_env_summary(),
        "recommended_python": "Python 3.10+ with requirements.txt installed",
    }


def _compact_arxiv_paper(paper: dict[str, Any], summary_limit: int = 1200) -> dict[str, Any]:
    summary = str(paper.get("summary", "") or "").replace("\n", " ").strip()
    return {
        "source": paper.get("source", "arxiv"),
        "entry_id": paper.get("entry_id", ""),
        "arxiv_id": paper.get("arxiv_id", ""),
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "published": paper.get("published", ""),
        "updated": paper.get("updated", ""),
        "pdf_url": paper.get("pdf_url", ""),
        "primary_category": paper.get("primary_category", ""),
        "categories": paper.get("categories", []),
        "summary": summary[:summary_limit],
        "summary_truncated": len(summary) > summary_limit,
        "watchlist_score": float(paper.get("watchlist_score", 0.0) or 0.0),
        "matched_watch_items": paper.get("matched_watch_items", []),
        "watchlist_reasons": paper.get("watchlist_reasons", []),
    }


def cmd_search_arxiv(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "") or "").strip()
    if not query:
        raise AgentToolError("query is empty.")

    max_results = _as_int(args.get("max_results"), 5, minimum=1, maximum=50)
    sort_by = str(args.get("sort_by", "relevance") or "relevance")
    include_watchlist = _as_bool(args.get("include_watchlist"), default=True)
    save_results = _as_bool(args.get("save_results"), default=True)

    from researchpilot.search.arxiv_search import search_arxiv_papers

    papers = search_arxiv_papers(query=query, max_results=max_results, sort_by=sort_by)

    if include_watchlist:
        try:
            from researchpilot.watchlist.watchlist_ranker import rank_papers_by_watchlist
            from researchpilot.watchlist.watchlist_store import load_watchlist

            papers = rank_papers_by_watchlist(papers, load_watchlist(), prioritize=True)
        except Exception:
            pass

    if save_results:
        _save_json(
            LAST_ARXIV_RESULTS_PATH,
            {
                "query": query,
                "sort_by": sort_by,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
                "results": papers,
            },
        )

    return {
        "query": query,
        "result_count": len(papers),
        "saved_to": str(LAST_ARXIV_RESULTS_PATH) if save_results else None,
        "results": [_compact_arxiv_paper(paper) for paper in papers],
    }


def cmd_plan_venue_collection(args: dict[str, Any]) -> dict[str, Any]:
    topic = str(args.get("topic", "") or "").strip()
    if not topic:
        raise AgentToolError("topic is empty.")

    from researchpilot.discovery.venue_collector import plan_venue_collection

    plan = plan_venue_collection(
        topic=topic,
        domains=_as_list(args.get("domains")),
        keywords=_as_list(args.get("keywords")),
        venues=_as_list(args.get("venues")),
        include_journals=_as_bool(args.get("include_journals"), default=True),
        max_venues=_as_int(args.get("max_venues"), 12, minimum=1, maximum=30),
    )
    return plan


def cmd_collect_venue_papers(args: dict[str, Any]) -> dict[str, Any]:
    topic = str(args.get("topic", "") or "").strip()
    if not topic:
        raise AgentToolError("topic is empty.")

    from researchpilot.discovery.venue_collector import collect_venue_papers

    raw_min_relevance_score = args.get("min_relevance_score", 1.0)
    if raw_min_relevance_score is None or raw_min_relevance_score == "":
        min_relevance_score = 1.0
    else:
        min_relevance_score = float(raw_min_relevance_score)

    collection = collect_venue_papers(
        topic=topic,
        domains=_as_list(args.get("domains")),
        keywords=_as_list(args.get("keywords")),
        venues=_as_list(args.get("venues")),
        years=_parse_int_list_arg(args.get("years")) or None,
        include_journals=_as_bool(args.get("include_journals"), default=True),
        max_venues=_as_int(args.get("max_venues"), 10, minimum=1, maximum=30),
        max_results_per_venue=_as_int(args.get("max_results_per_venue"), 8, minimum=1, maximum=50),
        max_total=_as_int(args.get("max_total"), 60, minimum=1, maximum=200),
        include_openreview=_as_bool(args.get("include_openreview"), default=True),
        include_openalex=_as_bool(args.get("include_openalex"), default=True),
        include_broad_openalex=_as_bool(args.get("include_broad_openalex"), default=True),
        include_semantic_scholar=_as_bool(args.get("include_semantic_scholar"), default=False),
        include_broad_semantic_scholar=_as_bool(args.get("include_broad_semantic_scholar"), default=True),
        min_relevance_score=min_relevance_score,
    )

    output_path = None
    if _as_bool(args.get("save"), default=True):
        output_path = _safe_artifact_name("venue_paper_collection", ".json")
        _save_json(output_path, collection)
        _save_json(LAST_VENUE_COLLECTION_PATH, collection)

    return {
        **collection,
        "saved_to": str(output_path) if output_path else None,
        "latest_path": str(LAST_VENUE_COLLECTION_PATH) if output_path else None,
    }


def cmd_download_pdf(args: dict[str, Any]) -> dict[str, Any]:
    pdf_url = str(args.get("pdf_url", "") or "").strip()
    if not pdf_url:
        raise AgentToolError("pdf_url is empty.")

    output_dir = str(args.get("output_dir", "data/uploads") or "data/uploads")
    filename = args.get("filename")

    from researchpilot.search.arxiv_search import download_pdf_from_url

    saved_path = download_pdf_from_url(
        pdf_url=pdf_url,
        output_dir=str(_resolve_project_path(output_dir)),
        filename=str(filename) if filename else None,
    )
    return {"saved_path": saved_path}


def cmd_download_arxiv_result(args: dict[str, Any]) -> dict[str, Any]:
    data = _load_json(LAST_ARXIV_RESULTS_PATH, {})
    results = data.get("results", []) if isinstance(data, dict) else []
    if not isinstance(results, list) or not results:
        raise AgentToolError("No saved arXiv results. Run search_arxiv first.")

    rank = _as_int(args.get("rank"), 1, minimum=1, maximum=len(results))
    output_dir = str(args.get("output_dir", "data/uploads") or "data/uploads")
    paper = results[rank - 1]

    from researchpilot.search.arxiv_search import download_arxiv_paper

    saved_path = download_arxiv_paper(paper, output_dir=str(_resolve_project_path(output_dir)))
    return {
        "rank": rank,
        "title": paper.get("title", ""),
        "arxiv_id": paper.get("arxiv_id", ""),
        "saved_path": saved_path,
    }


def cmd_ingest_pdf(args: dict[str, Any]) -> dict[str, Any]:
    pdf_path = _resolve_project_path(str(args.get("pdf_path", "") or ""), must_exist=True)
    paper_id = str(args.get("paper_id", "") or pdf_path.stem).strip()
    title = str(args.get("title", "") or paper_id).strip()
    chunk_size = _as_int(args.get("chunk_size"), 1200, minimum=200, maximum=8000)
    overlap = _as_int(args.get("overlap"), 200, minimum=0, maximum=chunk_size - 1)

    from researchpilot.ingest.chunker import chunk_pages
    from researchpilot.ingest.pdf_parser_pymupdf import parse_pdf

    pages = parse_pdf(str(pdf_path))
    chunks = chunk_pages(
        pages=pages,
        paper_id=paper_id,
        title=title,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    replace_meta = _replace_paper_chunks(paper_id, chunks)
    return {
        **replace_meta,
        "pdf_path": str(pdf_path),
        "title": title,
        "parsed_pages": len(pages),
        "chunk_size": chunk_size,
        "overlap": overlap,
    }


def cmd_ingest_text(args: dict[str, Any]) -> dict[str, Any]:
    paper_id = str(args.get("paper_id", "") or "").strip()
    if not paper_id:
        raise AgentToolError("paper_id is empty.")
    text = str(args.get("text", "") or "").strip()
    if not text:
        raise AgentToolError("text is empty.")

    title = str(args.get("title", "") or paper_id).strip()
    page = _as_int(args.get("page"), 1, minimum=1)
    chunk_size = _as_int(args.get("chunk_size"), 1200, minimum=200, maximum=8000)
    overlap = _as_int(args.get("overlap"), 200, minimum=0, maximum=chunk_size - 1)

    from researchpilot.ingest.chunker import chunk_pages
    from researchpilot.schemas import PageText

    chunks = chunk_pages(
        pages=[PageText(page=page, text=text)],
        paper_id=paper_id,
        title=title,
        chunk_size=chunk_size,
        overlap=overlap,
    )
    replace_meta = _replace_paper_chunks(paper_id, chunks)
    return {
        **replace_meta,
        "title": title,
        "page": page,
        "chunk_size": chunk_size,
        "overlap": overlap,
    }


def cmd_list_papers(args: dict[str, Any]) -> dict[str, Any]:
    chunk_dicts = _load_chunk_dicts()
    return {
        "chunk_count": len(chunk_dicts),
        "papers": _paper_summaries(chunk_dicts),
    }


def cmd_retrieve(args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query", "") or "").strip()
    if not query:
        raise AgentToolError("query is empty.")

    top_k = _as_int(args.get("top_k"), 5, minimum=1, maximum=30)
    mode = str(args.get("retrieval_mode", "bm25") or "bm25")
    retriever = _build_retriever(mode)
    evidence = retriever.search(query, top_k=top_k)
    return {
        "query": query,
        "retrieval_mode": mode,
        "evidence": _normalize_evidence(evidence, text_limit=None),
    }


def cmd_ask(args: dict[str, Any]) -> dict[str, Any]:
    question = str(args.get("question", "") or "").strip()
    if not question:
        raise AgentToolError("question is empty.")

    top_k = _as_int(args.get("top_k"), 8, minimum=1, maximum=30)
    mode = str(args.get("retrieval_mode", "bm25") or "bm25")
    retriever = _build_retriever(mode)
    evidence = retriever.search(question, top_k=top_k)

    from researchpilot.qa.answer_with_citations import generate_answer_with_citations

    answer = generate_answer_with_citations(question=question, evidence=evidence)
    return {
        "question": question,
        "retrieval_mode": mode,
        "answer": answer,
        "evidence": _normalize_evidence(evidence, text_limit=1600),
    }


def _paper_ids_from_args(args: dict[str, Any]) -> list[str]:
    explicit = _as_list(args.get("paper_ids"))
    if explicit:
        return explicit
    return [paper["paper_id"] for paper in _paper_summaries(_load_chunk_dicts())]


def _load_or_build_paper_cards(paper_ids: list[str], build_missing: bool) -> dict[str, dict[str, Any]]:
    from researchpilot.storage.corpus_store import get_cached_paper_card
    from researchpilot.storage.corpus_store import set_cached_paper_card

    chunks = _dicts_to_chunks(_load_chunk_dicts())
    chunks_by_paper: dict[str, list[Any]] = {}
    for chunk in chunks:
        chunks_by_paper.setdefault(chunk.paper_id, []).append(chunk)

    cards: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for paper_id in paper_ids:
        cached = get_cached_paper_card(paper_id)
        if isinstance(cached, dict):
            cards[paper_id] = cached
            continue
        if not build_missing:
            missing.append(paper_id)
            continue

        from researchpilot.cards.paper_card_generator import generate_paper_card

        card = generate_paper_card(paper_id=paper_id, chunks=chunks_by_paper.get(paper_id, []))
        set_cached_paper_card(paper_id, card)
        cards[paper_id] = card

    if missing:
        raise AgentToolError(f"Missing paper cards for: {', '.join(missing)}. Run paper_card or set build_missing_cards=true.")
    return cards


def _chunks_by_paper_id(paper_id: str) -> list[Any]:
    chunks = _dicts_to_chunks(_load_chunk_dicts())
    return [chunk for chunk in chunks if chunk.paper_id == paper_id]


def _normalize_agent_paper_card(card: dict[str, Any], paper_id: str) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for field in AGENT_CARD_FIELDS:
        if field == "paper_id":
            normalized[field] = str(card.get(field, paper_id) or paper_id)
            continue
        normalized[field] = str(card.get(field, "") or "")
    normalized["paper_id"] = paper_id
    return normalized


def cmd_prepare_paper_card(args: dict[str, Any]) -> dict[str, Any]:
    paper_id = str(args.get("paper_id", "") or "").strip()
    if not paper_id:
        raise AgentToolError("paper_id is empty.")

    max_chunks = _as_int(args.get("max_chunks"), 10, minimum=1, maximum=30)
    text_limit = _as_int(args.get("text_limit"), 1800, minimum=200, maximum=5000)
    paper_chunks = _chunks_by_paper_id(paper_id)
    if not paper_chunks:
        raise AgentToolError(f"No chunks found for paper_id: {paper_id}")

    evidence: list[dict[str, Any]] = []
    for idx, chunk in enumerate(paper_chunks[:max_chunks], start=1):
        text = str(chunk.text or "")
        evidence.append(
            {
                "label": f"C{idx}",
                "chunk_id": chunk.chunk_id,
                "paper_id": chunk.paper_id,
                "title": chunk.title,
                "page": chunk.page,
                "text": text[:text_limit],
                "truncated": len(text) > text_limit,
            }
        )

    return {
        "paper_id": paper_id,
        "mode": "agent_native",
        "schema": {field: "string" for field in AGENT_CARD_FIELDS},
        "instructions": (
            "Use the current agent model to generate one strict JSON object for a ResearchPilot paper card. "
            "Use only the provided evidence chunks. Do not invent datasets, results, or limitations. "
            "If a field is not supported by evidence, write an empty string or a conservative note. "
            "Return fields exactly: paper_id, title, problem, method, contribution, dataset, result, limitation, future_work, relevance."
        ),
        "evidence": evidence,
        "next_step": "Call save_paper_card with the JSON object produced by the agent.",
    }


def cmd_save_paper_card(args: dict[str, Any]) -> dict[str, Any]:
    card = _parse_json_object_arg(args, "card", "card_json")
    paper_id = str(args.get("paper_id", "") or card.get("paper_id", "") or "").strip()
    if not paper_id:
        raise AgentToolError("paper_id is empty.")

    normalized = _normalize_agent_paper_card(card, paper_id)

    from researchpilot.storage.corpus_store import set_cached_paper_card

    set_cached_paper_card(paper_id, normalized)
    return {
        "paper_id": paper_id,
        "card": normalized,
        "cache_path": str(PAPER_CARD_CACHE_PATH),
    }


def cmd_paper_card(args: dict[str, Any]) -> dict[str, Any]:
    paper_id = str(args.get("paper_id", "") or "").strip()
    if not paper_id:
        raise AgentToolError("paper_id is empty.")
    refresh = _as_bool(args.get("refresh"), default=False)

    cards = _load_or_build_paper_cards([paper_id], build_missing=True)
    if refresh:
        from researchpilot.cards.paper_card_generator import generate_paper_card
        from researchpilot.storage.corpus_store import set_cached_paper_card

        chunks = _dicts_to_chunks(_load_chunk_dicts())
        paper_chunks = [chunk for chunk in chunks if chunk.paper_id == paper_id]
        card = generate_paper_card(paper_id=paper_id, chunks=paper_chunks)
        set_cached_paper_card(paper_id, card)
        cards = {paper_id: card}

    return {
        "paper_id": paper_id,
        "card": cards[paper_id],
    }


def cmd_build_paper_cards(args: dict[str, Any]) -> dict[str, Any]:
    paper_ids = _paper_ids_from_args(args)
    if not paper_ids:
        raise AgentToolError("No paper_ids provided and no papers are ingested.")
    refresh = _as_bool(args.get("refresh"), default=False)
    cards = {}
    for paper_id in paper_ids:
        if refresh:
            cmd_paper_card({"paper_id": paper_id, "refresh": True})
        cards.update(_load_or_build_paper_cards([paper_id], build_missing=True))
    return {
        "paper_ids": paper_ids,
        "cards": cards,
        "cache_path": str(PAPER_CARD_CACHE_PATH),
    }


def cmd_comparison_table(args: dict[str, Any]) -> dict[str, Any]:
    paper_ids = _paper_ids_from_args(args)
    build_missing = _as_bool(args.get("build_missing_cards"), default=False)
    cards = _load_or_build_paper_cards(paper_ids, build_missing=build_missing)

    from researchpilot.cards.comparison_table import build_comparison_table

    table = build_comparison_table(cards)
    rows = table.to_dict(orient="records")
    csv_path = None
    if _as_bool(args.get("save_csv"), default=True):
        path = _safe_artifact_name("comparison_table", ".csv")
        path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False)
        csv_path = str(path)

    return {
        "paper_ids": paper_ids,
        "rows": rows,
        "csv_path": csv_path,
    }


def _load_venue_collection_arg(args: dict[str, Any]) -> dict[str, Any]:
    collection = args.get("collection")
    if isinstance(collection, dict):
        return collection

    raw_json = args.get("collection_json")
    if raw_json:
        parsed = json.loads(str(raw_json))
        if isinstance(parsed, dict):
            return parsed

    raw_path = args.get("collection_path")
    if raw_path:
        path = _resolve_project_path(str(raw_path), must_exist=True)
    else:
        path = LAST_VENUE_COLLECTION_PATH
    data = _load_json(path, {})
    if not isinstance(data, dict) or not isinstance(data.get("papers"), list):
        raise AgentToolError(
            f"No venue collection found. Run collect_venue_papers first or provide collection_path. Checked: {path}"
        )
    return data


def _compact_venue_collection(collection: dict[str, Any], max_papers: int, abstract_limit: int) -> dict[str, Any]:
    papers = collection.get("papers", [])
    if not isinstance(papers, list):
        papers = []
    compact_papers: list[dict[str, Any]] = []
    for idx, paper in enumerate(papers[:max_papers], start=1):
        if not isinstance(paper, dict):
            continue
        abstract = str(paper.get("abstract", "") or "").replace("\n", " ").strip()
        compact_papers.append(
            {
                "rank": idx,
                "title": paper.get("title", ""),
                "authors": paper.get("authors", []),
                "year": paper.get("year"),
                "venue": paper.get("venue", ""),
                "venue_rank": paper.get("venue_rank", ""),
                "venue_field": paper.get("venue_field", ""),
                "target_venue": paper.get("target_venue", paper.get("venue", "")),
                "target_venue_rank": paper.get("target_venue_rank", paper.get("venue_rank", "")),
                "target_venue_field": paper.get("target_venue_field", paper.get("venue_field", "")),
                "matched_selected_venue": paper.get("matched_selected_venue"),
                "collection_scope": paper.get("collection_scope", ""),
                "source": paper.get("source", ""),
                "source_url": paper.get("source_url", ""),
                "pdf_url": paper.get("pdf_url", ""),
                "doi": paper.get("doi", ""),
                "semantic_scholar_paper_id": paper.get("semantic_scholar_paper_id", ""),
                "cited_by_count": paper.get("cited_by_count"),
                "relevance_score": paper.get("relevance_score", 0.0),
                "matched_keywords": paper.get("matched_keywords", []),
                "domain_matches": paper.get("domain_matches", []),
                "abstract": abstract[:abstract_limit],
                "abstract_truncated": len(abstract) > abstract_limit,
            }
        )

    plan = collection.get("plan", {})
    if not isinstance(plan, dict):
        plan = {}
    return {
        "topic": collection.get("topic", ""),
        "collected_at": collection.get("collected_at", ""),
        "years": collection.get("years", []),
        "domains": plan.get("domains", []),
        "keywords": plan.get("keywords", []),
        "venues": plan.get("venues", []),
        "paper_count": collection.get("paper_count", len(papers)),
        "papers": compact_papers,
        "warnings": collection.get("warnings", []),
        "scholar_followup_urls": plan.get("scholar_followup_urls", []),
    }


def cmd_prepare_venue_paper_summary(args: dict[str, Any]) -> dict[str, Any]:
    collection = _load_venue_collection_arg(args)
    max_papers = _as_int(args.get("max_papers"), 25, minimum=1, maximum=80)
    abstract_limit = _as_int(args.get("abstract_limit"), 900, minimum=120, maximum=3000)
    compact = _compact_venue_collection(collection, max_papers=max_papers, abstract_limit=abstract_limit)
    focus = str(args.get("focus", "") or compact.get("topic", "") or "").strip()
    return {
        "mode": "agent_native",
        "focus": focus,
        "collection": compact,
        "instructions": (
            "Use the current agent model to write a Chinese Markdown survey-style summary from this venue/journal collection. "
            "Use only the supplied metadata and abstracts. Structure the output as: # 论文搜集报告; "
            "## 1. 检索范围与来源; ## 2. CCF相关会议/期刊覆盖; ## 3. 代表性论文; "
            "## 4. 主题聚类; ## 5. 交叉方向观察; ## 6. 可能遗漏与Google Scholar补查链接; ## 7. 后续精读建议. "
            "Mention venue rank hints, Semantic Scholar/OpenReview/OpenAlex/source URLs, and uncertainty when metadata is thin. "
            "Do not claim exhaustive coverage."
        ),
        "next_step": "Call save_artifact with artifact_type='venue_paper_summary' and the Markdown generated by the agent.",
    }


def cmd_venue_paper_summary(args: dict[str, Any]) -> dict[str, Any]:
    collection = _load_venue_collection_arg(args)
    max_papers = _as_int(args.get("max_papers"), 25, minimum=1, maximum=80)
    abstract_limit = _as_int(args.get("abstract_limit"), 900, minimum=120, maximum=3000)
    compact = _compact_venue_collection(collection, max_papers=max_papers, abstract_limit=abstract_limit)

    from researchpilot.llm.openai_client import chat_completion

    system_prompt = (
        "你是严谨的科研文献调研助手。只能基于用户提供的会议/期刊论文元数据和摘要写作。"
        "输出中文 Markdown；不得声称检索已穷尽；对 CCF 等级只作为目录提示。"
    )
    user_prompt = (
        "请基于以下 venue/journal collection 生成论文搜集报告。\n\n"
        f"{json.dumps(compact, ensure_ascii=False, indent=2)}\n\n"
        "结构：# 论文搜集报告；## 1. 检索范围与来源；## 2. CCF相关会议/期刊覆盖；"
        "## 3. 代表性论文；## 4. 主题聚类；## 5. 交叉方向观察；"
        "## 6. 可能遗漏与Google Scholar补查链接；## 7. 后续精读建议。"
    )
    summary = chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    output_path = _write_text_artifact("venue_paper_summary", summary, ".md") if _as_bool(args.get("save"), default=True) else None
    return {
        "summary": summary,
        "output_path": output_path,
    }


def cmd_metadata_paper_cards(args: dict[str, Any]) -> dict[str, Any]:
    collection = _load_venue_collection_arg(args)
    papers = collection.get("papers", [])
    if not isinstance(papers, list) or not papers:
        raise AgentToolError("No papers found in venue collection.")

    raw_indices = _as_list(args.get("paper_indices"))
    selected_indices: list[int] = []
    for item in raw_indices:
        try:
            index = int(item)
        except Exception:
            continue
        if 1 <= index <= len(papers) and index - 1 not in selected_indices:
            selected_indices.append(index - 1)
    if not selected_indices:
        max_cards = _as_int(args.get("max_cards"), 10, minimum=1, maximum=80)
        selected_indices = list(range(min(max_cards, len(papers))))

    from researchpilot.cards.metadata_cards import paper_card_from_metadata
    from researchpilot.storage.corpus_store import set_cached_paper_card

    topic = str(args.get("topic", "") or collection.get("topic", "") or "")
    cards: dict[str, dict[str, Any]] = {}
    for index in selected_indices:
        paper = papers[index]
        if not isinstance(paper, dict):
            continue
        card = paper_card_from_metadata(paper, topic=topic)
        paper_id = str(card.get("paper_id", "") or "")
        if not paper_id:
            continue
        set_cached_paper_card(paper_id, card)
        cards[paper_id] = card

    return {
        "topic": topic,
        "paper_indices": [index + 1 for index in selected_indices],
        "card_count": len(cards),
        "cards": cards,
        "cache_path": str(PAPER_CARD_CACHE_PATH),
    }


def cmd_prepare_literature_review(args: dict[str, Any]) -> dict[str, Any]:
    topic = str(args.get("topic", "") or "").strip()
    if not topic:
        raise AgentToolError("topic is empty.")
    paper_ids = _paper_ids_from_args(args)
    cards = _load_or_build_paper_cards(paper_ids, build_missing=False)
    return {
        "topic": topic,
        "paper_ids": paper_ids,
        "paper_cards": cards,
        "mode": "agent_native",
        "instructions": (
            "Use the current agent model to write a conservative Chinese Markdown literature review from these paper cards only. "
            "Keep the structure: # 文献综述：{topic}; ## 1. 研究背景; ## 2. 现有方法分类; ## 3. 代表性工作比较; "
            "## 4. 当前局限; ## 5. Research Gaps; ## 6. Future Directions. "
            "Add source hints using paper_id or title after key claims. Do not introduce facts absent from the cards."
        ),
        "next_step": "Call save_artifact with artifact_type='literature_review' and the Markdown generated by the agent.",
    }


def cmd_literature_review(args: dict[str, Any]) -> dict[str, Any]:
    topic = str(args.get("topic", "") or "").strip()
    if not topic:
        raise AgentToolError("topic is empty.")
    paper_ids = _paper_ids_from_args(args)
    build_missing = _as_bool(args.get("build_missing_cards"), default=True)
    cards = _load_or_build_paper_cards(paper_ids, build_missing=build_missing)

    from researchpilot.review.lit_review_generator import generate_literature_review

    review = generate_literature_review(topic=topic, paper_cards=cards)
    output_path = _write_text_artifact("literature_review", review, ".md") if _as_bool(args.get("save"), default=True) else None
    return {
        "topic": topic,
        "paper_ids": paper_ids,
        "review": review,
        "output_path": output_path,
    }


def _fallback_claims_from_review(review_text: str) -> list[str]:
    claims: list[str] = []
    for raw in re.split(r"[\n。！？!?]+", review_text):
        sentence = raw.strip()
        if not sentence or sentence.startswith("#"):
            continue
        sentence = re.sub(r"^\s*[-*]\s+", "", sentence).strip()
        if len(sentence) < 12:
            continue
        claims.append(sentence)
        if len(claims) >= 12:
            break
    return claims


def cmd_prepare_review_verification(args: dict[str, Any]) -> dict[str, Any]:
    review_text = _read_text_arg(args, "review_text", "review_path")
    top_k = _as_int(args.get("top_k"), 5, minimum=1, maximum=12)
    retrieval_mode = str(args.get("retrieval_mode", "bm25") or "bm25")
    retriever = _build_retriever(retrieval_mode)
    claims = _fallback_claims_from_review(review_text)

    items: list[dict[str, Any]] = []
    for idx, claim in enumerate(claims, start=1):
        evidence = retriever.search(claim, top_k=top_k)
        items.append(
            {
                "idx": idx,
                "claim": claim,
                "evidence": _normalize_evidence(evidence, text_limit=1200),
            }
        )

    return {
        "mode": "agent_native",
        "retrieval_mode": retrieval_mode,
        "claim_count": len(items),
        "items": items,
        "instructions": (
            "Use the current agent model to judge each claim using only the provided evidence. "
            "For each item, output claim, status, reason, best_evidence, evidence, and suggested_rewrite. "
            "status must be one of supported, weakly_supported, unsupported. "
            "For weakly_supported or unsupported claims, write a conservative suggested_rewrite or say that evidence is insufficient."
        ),
        "next_step": "Call save_claim_verification with the JSON list produced by the agent.",
    }


def _compact_verification_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for item in results:
        evidence = []
        for ev in item.get("evidence", []) or []:
            ev_text = str(ev.get("text", "") or "")
            evidence.append(
                {
                    "rank": ev.get("rank"),
                    "paper_id": ev.get("paper_id", ""),
                    "page": ev.get("page", ""),
                    "score": float(ev.get("score", 0.0) or 0.0),
                    "chunk_id": ev.get("chunk_id", ""),
                    "text_preview": ev_text[:500],
                    "truncated": len(ev_text) > 500,
                }
            )
        compacted.append(
            {
                "claim": item.get("claim", ""),
                "status": item.get("status", ""),
                "reason": item.get("reason", ""),
                "best_evidence": item.get("best_evidence", []),
                "source_hints": item.get("source_hints", []),
                "suggested_rewrite": item.get("suggested_rewrite", ""),
                "evidence": evidence,
            }
        )
    return compacted


def cmd_verify_review(args: dict[str, Any]) -> dict[str, Any]:
    review_text = _read_text_arg(args, "review_text", "review_path")
    top_k = _as_int(args.get("top_k"), 5, minimum=1, maximum=12)
    verification_mode = str(args.get("verification_mode", "balanced") or "balanced")
    retrieval_mode = str(args.get("retrieval_mode", "bm25") or "bm25")
    max_per_paper = _as_int(args.get("max_per_paper"), 2, minimum=1, maximum=10)
    retriever = _build_retriever(retrieval_mode)

    paper_ids = _paper_ids_from_args(args)
    build_missing = _as_bool(args.get("build_missing_cards"), default=False)
    try:
        paper_cards = _load_or_build_paper_cards(paper_ids, build_missing=build_missing)
    except AgentToolError:
        paper_cards = {}

    from researchpilot.verify.claim_verifier import verify_review_claims

    results = verify_review_claims(
        review_text=review_text,
        retriever=retriever,
        top_k=top_k,
        verification_mode=verification_mode,
        diversify_evidence=_as_bool(args.get("diversify_evidence"), default=True),
        max_per_paper=max_per_paper,
        source_first=_as_bool(args.get("source_first"), default=True),
        source_only_when_available=_as_bool(args.get("source_only_when_available"), default=True),
        paper_cards=paper_cards or None,
    )
    counts = Counter(str(item.get("status", "")) for item in results)
    output_path = None
    if _as_bool(args.get("save"), default=True):
        output_path = _safe_artifact_name("claim_verification", ".json")
        _save_json(output_path, results)
        _save_json(OUTPUT_DIR / "latest_claim_verification.json", results)

    return {
        "verification_mode": verification_mode,
        "retrieval_mode": retrieval_mode,
        "claim_count": len(results),
        "counts": dict(counts),
        "output_path": str(output_path) if output_path else None,
        "results": _compact_verification_results(results),
    }


def cmd_save_claim_verification(args: dict[str, Any]) -> dict[str, Any]:
    results = _parse_json_list_arg(args, "results", "results_json")
    allowed = {"supported", "weakly_supported", "unsupported"}
    normalized: list[dict[str, Any]] = []
    for item in results:
        claim = str(item.get("claim", "") or "").strip()
        if not claim:
            continue
        status = str(item.get("status", "weakly_supported") or "weakly_supported").strip()
        if status not in allowed:
            status = "weakly_supported"
        normalized.append(
            {
                "claim": claim,
                "status": status,
                "reason": str(item.get("reason", "") or ""),
                "best_evidence": item.get("best_evidence", []) if isinstance(item.get("best_evidence", []), list) else [],
                "evidence": item.get("evidence", []) if isinstance(item.get("evidence", []), list) else [],
                "suggested_rewrite": str(item.get("suggested_rewrite", "") or ""),
                "source_hints": item.get("source_hints", []) if isinstance(item.get("source_hints", []), list) else [],
            }
        )

    output_path = _safe_artifact_name("claim_verification", ".json")
    _save_json(output_path, normalized)
    _save_json(OUTPUT_DIR / "latest_claim_verification.json", normalized)
    counts = Counter(str(item.get("status", "")) for item in normalized)
    return {
        "claim_count": len(normalized),
        "counts": dict(counts),
        "output_path": str(output_path),
    }


def _load_verification_arg(args: dict[str, Any]) -> list[dict[str, Any]]:
    raw_results = args.get("verification_results")
    if isinstance(raw_results, list):
        return [item for item in raw_results if isinstance(item, dict)]

    raw_path = args.get("verification_path")
    if raw_path:
        path = _resolve_project_path(str(raw_path), must_exist=True)
    else:
        path = OUTPUT_DIR / "latest_claim_verification.json"
    data = _load_json(path, [])
    if not isinstance(data, list):
        raise AgentToolError(f"Verification file is not a JSON list: {path}")
    return [item for item in data if isinstance(item, dict)]


def cmd_rewrite_review(args: dict[str, Any]) -> dict[str, Any]:
    original_review = _read_text_arg(args, "original_review", "original_review_path")
    verification = _load_verification_arg(args)

    from researchpilot.review.revised_review_generator import generate_revised_literature_review

    revised = generate_revised_literature_review(
        original_review=original_review,
        claim_verification=verification,
    )
    output_path = _write_text_artifact("revised_literature_review", revised, ".md") if _as_bool(args.get("save"), default=True) else None
    return {
        "revised_review": revised,
        "output_path": output_path,
    }


def cmd_prepare_research_ideas(args: dict[str, Any]) -> dict[str, Any]:
    topic = str(args.get("topic", "") or "").strip() or None
    paper_ids = _paper_ids_from_args(args)
    cards = _load_or_build_paper_cards(paper_ids, build_missing=False)

    literature_review = ""
    if args.get("literature_review") or args.get("literature_review_path"):
        literature_review = _read_text_arg(args, "literature_review", "literature_review_path")

    revised_review = ""
    if args.get("revised_literature_review") or args.get("revised_literature_review_path"):
        revised_review = _read_text_arg(args, "revised_literature_review", "revised_literature_review_path")

    claim_verification = None
    if args.get("verification_results") or args.get("verification_path"):
        claim_verification = _load_verification_arg(args)

    num_ideas = _as_int(args.get("num_ideas"), 5, minimum=1, maximum=8)
    return {
        "mode": "agent_native",
        "topic": topic,
        "paper_ids": paper_ids,
        "paper_cards": cards,
        "literature_review": literature_review,
        "revised_literature_review": revised_review,
        "claim_verification": claim_verification,
        "num_ideas": num_ideas,
        "instructions": (
            "Use the current agent model to generate candidate future research ideas in Chinese Markdown. "
            "Base ideas only on paper cards, reviews, and verification signals supplied here. "
            "Prefer limitations, research gaps, weak/unsupported claims, and suggested rewrites. "
            "For each idea include Motivation, Research Gap, Proposed Method, Why It May Be Novel, Required Evidence or Experiments, Risks, and Related Existing Work."
        ),
        "next_step": "Call save_artifact with artifact_type='research_ideas' and the Markdown generated by the agent.",
    }


def cmd_research_ideas(args: dict[str, Any]) -> dict[str, Any]:
    topic = str(args.get("topic", "") or "").strip() or None
    paper_ids = _paper_ids_from_args(args)
    build_missing = _as_bool(args.get("build_missing_cards"), default=False)
    cards = _load_or_build_paper_cards(paper_ids, build_missing=build_missing)

    literature_review = ""
    if args.get("literature_review") or args.get("literature_review_path"):
        literature_review = _read_text_arg(args, "literature_review", "literature_review_path")

    revised_review = ""
    if args.get("revised_literature_review") or args.get("revised_literature_review_path"):
        revised_review = _read_text_arg(args, "revised_literature_review", "revised_literature_review_path")

    claim_verification = None
    if args.get("verification_results") or args.get("verification_path"):
        claim_verification = _load_verification_arg(args)

    num_ideas = _as_int(args.get("num_ideas"), 5, minimum=1, maximum=8)

    from researchpilot.review.research_idea_generator import generate_research_ideas

    ideas = generate_research_ideas(
        topic=topic,
        paper_cards=cards,
        literature_review=literature_review,
        revised_literature_review=revised_review,
        claim_verification=claim_verification,
        num_ideas=num_ideas,
    )
    output_path = _write_text_artifact("research_ideas", ideas, ".md") if _as_bool(args.get("save"), default=True) else None
    return {
        "topic": topic,
        "paper_ids": paper_ids,
        "ideas": ideas,
        "output_path": output_path,
    }


def cmd_save_artifact(args: dict[str, Any]) -> dict[str, Any]:
    artifact_type = str(args.get("artifact_type", "agent_artifact") or "agent_artifact").strip()
    text = str(args.get("text", "") or "")
    if not text.strip():
        text = _read_text_arg(args, "text", "path")
    suffix = str(args.get("suffix", ".md") or ".md").strip()
    if not suffix.startswith("."):
        suffix = f".{suffix}"

    output_path = _write_text_artifact(artifact_type, text, suffix)
    return {
        "artifact_type": artifact_type,
        "output_path": output_path,
        "latest_path": str(OUTPUT_DIR / f"latest_{re.sub(r'[^A-Za-z0-9_.-]+', '_', artifact_type).strip('._-')}{suffix}"),
    }


def cmd_watchlist(args: dict[str, Any]) -> dict[str, Any]:
    operation = str(args.get("operation", "list") or "list").strip().lower()

    from researchpilot.watchlist.watchlist_store import add_watch_item
    from researchpilot.watchlist.watchlist_store import delete_watch_item
    from researchpilot.watchlist.watchlist_store import load_watchlist

    if operation == "list":
        return {"watchlist": load_watchlist()}

    if operation == "add":
        item = args.get("item")
        if not isinstance(item, dict):
            raise AgentToolError("watchlist add requires item object.")
        return {"watchlist": add_watch_item(item)}

    if operation == "delete":
        index = _as_int(args.get("index"), -1)
        return {"watchlist": delete_watch_item(index)}

    if operation == "rank_last_search":
        data = _load_json(LAST_ARXIV_RESULTS_PATH, {})
        papers = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(papers, list) or not papers:
            raise AgentToolError("No saved arXiv results. Run search_arxiv first.")
        from researchpilot.watchlist.watchlist_ranker import rank_papers_by_watchlist

        ranked = rank_papers_by_watchlist(papers, load_watchlist(), prioritize=True)
        _save_json(
            LAST_ARXIV_RESULTS_PATH,
            {
                **data,
                "results": ranked,
                "reranked_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        return {"results": [_compact_arxiv_paper(paper) for paper in ranked]}

    if operation == "summarize_last_search":
        data = _load_json(LAST_ARXIV_RESULTS_PATH, {})
        papers = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(papers, list) or not papers:
            raise AgentToolError("No saved arXiv results. Run search_arxiv first.")

        from researchpilot.watchlist.watchlist_summary import summarize_watchlist_trends

        summary = summarize_watchlist_trends(
            papers=papers,
            watchlist=load_watchlist(),
            topic=str(data.get("query", "") or args.get("topic", "") or ""),
            max_papers=_as_int(args.get("max_papers"), 8, minimum=1, maximum=20),
        )
        output_path = _write_text_artifact("watchlist_summary", summary, ".md") if _as_bool(args.get("save"), default=True) else None
        return {"summary": summary, "output_path": output_path}

    raise AgentToolError(f"Unknown watchlist operation: {operation}")


COMMANDS = {
    "status": cmd_status,
    "search_arxiv": cmd_search_arxiv,
    "plan_venue_collection": cmd_plan_venue_collection,
    "collect_venue_papers": cmd_collect_venue_papers,
    "download_pdf": cmd_download_pdf,
    "download_arxiv_result": cmd_download_arxiv_result,
    "ingest_pdf": cmd_ingest_pdf,
    "ingest_text": cmd_ingest_text,
    "list_papers": cmd_list_papers,
    "retrieve": cmd_retrieve,
    "ask": cmd_ask,
    "prepare_paper_card": cmd_prepare_paper_card,
    "save_paper_card": cmd_save_paper_card,
    "paper_card": cmd_paper_card,
    "build_paper_cards": cmd_build_paper_cards,
    "comparison_table": cmd_comparison_table,
    "prepare_venue_paper_summary": cmd_prepare_venue_paper_summary,
    "venue_paper_summary": cmd_venue_paper_summary,
    "metadata_paper_cards": cmd_metadata_paper_cards,
    "prepare_literature_review": cmd_prepare_literature_review,
    "literature_review": cmd_literature_review,
    "prepare_review_verification": cmd_prepare_review_verification,
    "verify_review": cmd_verify_review,
    "save_claim_verification": cmd_save_claim_verification,
    "rewrite_review": cmd_rewrite_review,
    "prepare_research_ideas": cmd_prepare_research_ideas,
    "research_ideas": cmd_research_ideas,
    "save_artifact": cmd_save_artifact,
    "watchlist": cmd_watchlist,
}


def dispatch(command: str, args: dict[str, Any]) -> dict[str, Any]:
    handler = COMMANDS.get(command)
    if handler is None:
        raise AgentToolError(f"Unknown command: {command}")
    result = handler(args)
    return {
        "ok": True,
        "command": command,
        **result,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _write_json(
            {
                "ok": False,
                "error": "Usage: python -m researchpilot.agent_cli <command> [json-args] or tool <command>",
                "commands": sorted(COMMANDS),
            }
        )
        return 1

    try:
        if argv[1] == "tool":
            if len(argv) < 3:
                raise AgentToolError("Missing tool command.")
            command = argv[2]
            args = _read_json_stdin()
        else:
            command = argv[1]
            args = json.loads(argv[2]) if len(argv) >= 3 else {}
            if not isinstance(args, dict):
                raise AgentToolError("Command args must be a JSON object.")

        _write_json(dispatch(command, args))
        return 0
    except Exception as exc:
        payload: dict[str, Any] = {
            "ok": False,
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
        if os.getenv("RESEARCHPILOT_AGENT_DEBUG"):
            payload["traceback"] = traceback.format_exc()
        _write_json(payload)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
