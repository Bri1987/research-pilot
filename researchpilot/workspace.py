from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = PROJECT_ROOT / "data" / "outputs" / "workspace"
AGENT_STATE_DIR = PROJECT_ROOT / "data" / "agent_state"
AGENT_OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs" / "agent"
LAST_VENUE_COLLECTION_PATH = AGENT_STATE_DIR / "last_venue_collection.json"
CHUNKS_PATH = AGENT_STATE_DIR / "chunks.json"


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.\-\u4e00-\u9fff]+", "_", str(value or "")).strip("._-")
    return safe[:80] or "report"


def load_json(path: str | Path, default: Any) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        return default
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_workspace_report(
    title: str,
    content: str,
    *,
    kind: str = "report",
) -> Path:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = WORKSPACE_DIR / f"{_safe_name(kind)}_{_safe_name(title)}_{stamp}.md"
    path.write_text(str(content or ""), encoding="utf-8")
    latest = WORKSPACE_DIR / f"latest_{_safe_name(kind)}.md"
    latest.write_text(str(content or ""), encoding="utf-8")
    return path


def list_workspace_reports(limit: int = 20) -> list[dict[str, Any]]:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for path in sorted(WORKSPACE_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            text = ""
        rows.append(
            {
                "name": path.name,
                "path": str(path),
                "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                "preview": text[:800],
            }
        )
        if len(rows) >= limit:
            break
    return rows


def load_agent_paper_summaries(limit: int = 80) -> list[dict[str, Any]]:
    chunks = load_json(CHUNKS_PATH, [])
    if not isinstance(chunks, list):
        return []
    grouped: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        paper_id = str(chunk.get("paper_id", "") or "")
        if not paper_id:
            continue
        row = grouped.setdefault(
            paper_id,
            {
                "paper_id": paper_id,
                "title": chunk.get("title") or paper_id,
                "chunk_count": 0,
                "text_chars": 0,
                "sample": "",
            },
        )
        row["chunk_count"] += 1
        text = str(chunk.get("text", "") or "")
        row["text_chars"] += len(text)
        if not row["sample"] and text.strip():
            row["sample"] = text[:600]
    return sorted(grouped.values(), key=lambda item: item["paper_id"])[:limit]


def load_latest_venue_collection() -> dict[str, Any]:
    data = load_json(LAST_VENUE_COLLECTION_PATH, {})
    return data if isinstance(data, dict) else {}


def workspace_context_payload(
    *,
    paper_cards: dict[str, dict],
    watchlist: list[dict],
    max_cards: int = 30,
    max_reports: int = 8,
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    for paper_id, card in list(paper_cards.items())[:max_cards]:
        if not isinstance(card, dict):
            continue
        cards.append(
            {
                "paper_id": paper_id,
                "title": card.get("title", ""),
                "problem": card.get("problem", ""),
                "method": card.get("method", ""),
                "contribution": card.get("contribution", ""),
                "result": card.get("result", ""),
                "limitation": card.get("limitation", ""),
                "relevance": card.get("relevance", ""),
                "source_metadata": card.get("source_metadata", {}),
            }
        )

    latest_collection = load_latest_venue_collection()
    collection_summary: dict[str, Any] = {}
    if latest_collection:
        papers = latest_collection.get("papers", [])
        if not isinstance(papers, list):
            papers = []
        collection_summary = {
            "topic": latest_collection.get("topic", ""),
            "collected_at": latest_collection.get("collected_at", ""),
            "paper_count": latest_collection.get("paper_count", len(papers)),
            "sample_papers": [
                {
                    "title": item.get("title", ""),
                    "venue": item.get("venue", ""),
                    "target_venue": item.get("target_venue", ""),
                    "source": item.get("source", ""),
                    "year": item.get("year"),
                    "abstract": str(item.get("abstract", "") or "")[:500],
                }
                for item in papers[:20]
                if isinstance(item, dict)
            ],
        }

    return {
        "paper_cards": cards,
        "watchlist": watchlist[:30],
        "ingested_papers": load_agent_paper_summaries(limit=80),
        "latest_venue_collection": collection_summary,
        "workspace_reports": list_workspace_reports(limit=max_reports),
    }
