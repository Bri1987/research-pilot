from __future__ import annotations

import hashlib
import re
from typing import Any


CARD_FIELDS = [
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


def normalize_doi(value: Any) -> str:
    doi = str(value or "").strip().lower()
    if not doi:
        return ""
    doi = re.sub(r"^doi\s*:\s*", "", doi)
    doi = re.sub(r"^(?:https?://)?(?:dx\.)?doi\.org/", "", doi)
    return doi.strip()


def metadata_paper_id(paper: dict[str, Any]) -> str:
    doi = normalize_doi(paper.get("doi"))
    if doi:
        return f"doi:{doi}"

    arxiv_id = str(paper.get("arxiv_id", "") or "").strip()
    if arxiv_id:
        return f"arxiv:{arxiv_id}"

    s2_id = str(paper.get("semantic_scholar_paper_id", "") or "").strip()
    if s2_id:
        return f"s2:{s2_id}"

    openalex_id = str(paper.get("openalex_id", "") or "").strip().rstrip("/")
    if openalex_id:
        return f"openalex:{openalex_id.rsplit('/', 1)[-1]}"

    source_url = str(paper.get("source_url", "") or "").strip()
    if source_url:
        digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:12]
        return f"url:{digest}"

    title = str(paper.get("title", "") or "").strip()
    digest = hashlib.sha1(title.encode("utf-8")).hexdigest()[:12] if title else "unknown"
    return f"metadata:{digest}"


def _compact_text(value: Any, limit: int = 900) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def paper_card_from_metadata(paper: dict[str, Any], topic: str = "") -> dict[str, Any]:
    paper_id = metadata_paper_id(paper)
    title = str(paper.get("title", "") or paper_id).strip()
    venue = str(paper.get("venue", "") or paper.get("target_venue", "") or "").strip()
    source = str(paper.get("source", "") or "").strip()
    year = str(paper.get("year", "") or "").strip()
    abstract = _compact_text(paper.get("abstract", ""), limit=1000)
    keywords = paper.get("matched_keywords", []) or []
    relevance_bits = []
    if topic:
        relevance_bits.append(f"Matches the collection topic: {topic}.")
    if venue:
        relevance_bits.append(f"Venue/source: {venue}.")
    if source:
        relevance_bits.append(f"Collected from {source}.")
    if keywords:
        relevance_bits.append(f"Matched keywords: {', '.join(map(str, keywords[:8]))}.")
    if paper.get("source_url"):
        relevance_bits.append(f"Source URL: {paper.get('source_url')}.")

    abstract_note = f" Metadata abstract: {abstract}" if abstract else ""
    card = {
        "paper_id": paper_id,
        "title": title,
        "problem": (
            f"Metadata-level candidate for {topic or 'the selected research topic'}."
            f"{abstract_note}"
        ).strip(),
        "method": "Not reliably extractable from metadata alone; inspect the full text before making method claims.",
        "contribution": "Not reliably extractable from metadata alone; use this as a discovery card until the paper is ingested or read.",
        "dataset": "Not specified in collected metadata.",
        "result": "Not specified in collected metadata.",
        "limitation": "This card is generated from venue/search metadata and abstract snippets, not from full-paper evidence.",
        "future_work": "Download or ingest the paper PDF, then regenerate a full evidence-grounded card.",
        "relevance": " ".join(relevance_bits).strip(),
        "source_metadata": {
            "source": source,
            "source_url": paper.get("source_url", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "venue": venue,
            "target_venue": paper.get("target_venue", ""),
            "year": year,
            "doi": paper.get("doi", ""),
            "semantic_scholar_paper_id": paper.get("semantic_scholar_paper_id", ""),
            "collection_scope": paper.get("collection_scope", ""),
        },
        "zh": {
            "title": title,
            "problem": (
                f"这是一篇围绕“{topic or '当前研究主题'}”搜集到的元数据级候选论文。"
                f"{' 摘要线索：' + abstract if abstract else ''}"
            ).strip(),
            "method": "仅凭元数据无法可靠判断方法细节；需要下载或入库全文后再生成证据支撑的完整卡片。",
            "contribution": "当前只能判断其与主题相关，具体贡献需结合全文确认。",
            "dataset": "采集到的元数据中未明确数据集或基准。",
            "result": "采集到的元数据中未明确实验结果或形式化结论。",
            "limitation": "该卡片基于检索元数据和摘要片段生成，不等价于全文精读结论。",
            "future_work": "建议下载 PDF 并 ingest 后重新生成完整 paper card。",
            "relevance": "；".join(
                item
                for item in [
                    f"主题：{topic}" if topic else "",
                    f"来源/会议期刊：{venue}" if venue else "",
                    f"采集源：{source}" if source else "",
                    f"命中关键词：{', '.join(map(str, keywords[:8]))}" if keywords else "",
                ]
                if item
            ),
        },
    }
    return card
