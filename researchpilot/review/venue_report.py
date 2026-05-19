from __future__ import annotations

from collections import defaultdict
from typing import Any


def _compact(value: Any, limit: int = 800) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def deterministic_venue_report(
    collection: dict[str, Any],
    *,
    focus: str = "",
    max_papers: int = 25,
) -> str:
    topic = str(focus or collection.get("topic", "") or "未命名主题").strip()
    plan = collection.get("plan", {})
    if not isinstance(plan, dict):
        plan = {}
    papers = collection.get("papers", [])
    if not isinstance(papers, list):
        papers = []
    papers = [paper for paper in papers if isinstance(paper, dict)]
    selected = papers[:max_papers]

    venue_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_groups: dict[str, int] = defaultdict(int)
    scope_groups: dict[str, int] = defaultdict(int)
    for paper in selected:
        venue = str(paper.get("target_venue") or paper.get("venue") or "Unknown")
        venue_groups[venue].append(paper)
        source_groups[str(paper.get("source") or "unknown")] += 1
        scope_groups[str(paper.get("collection_scope") or "unknown")] += 1

    lines = [
        f"# 论文搜集报告：{topic}",
        "",
        "## 1. 检索范围与来源",
        f"- 主题：{topic}",
        f"- 年份范围：{collection.get('years', [])}",
        f"- 领域推断：{plan.get('domains', [])}",
        f"- 关键词：{plan.get('keywords', [])}",
        f"- 返回论文数：{collection.get('paper_count', len(papers))}",
        f"- 本报告预览论文数：{len(selected)}",
        "",
        "来源计数：" if source_groups else "来源计数：暂无",
    ]
    for source, count in sorted(source_groups.items()):
        lines.append(f"- {source}: {count}")

    lines.extend(["", "范围语义："])
    for scope, count in sorted(scope_groups.items()):
        if scope == "broad_openalex":
            note = "相关命中，不应表述为目标会议/期刊正式论文"
        elif scope == "broad_semantic_scholar":
            note = "Semantic Scholar 主题检索命中，需要人工确认 venue 归属"
        else:
            note = "目标 venue/source 命中"
        lines.append(f"- {scope}: {count}（{note}）")

    lines.extend(["", "## 2. CCF 相关会议/期刊覆盖"])
    venues = plan.get("venues", [])
    if isinstance(venues, list) and venues:
        for venue in venues[:20]:
            if not isinstance(venue, dict):
                continue
            lines.append(
                f"- {venue.get('acronym', '')}: {venue.get('name', '')} "
                f"({venue.get('ccf_rank', '')}, {venue.get('ccf_field', '')}, {venue.get('kind', '')})"
            )
    else:
        lines.append("- 暂无 venue 规划信息。")

    lines.extend(["", "## 3. 代表性论文"])
    if not selected:
        lines.append("暂无可展示论文。")
    for idx, paper in enumerate(selected, start=1):
        title = paper.get("title", "")
        venue = paper.get("venue", "")
        target = paper.get("target_venue", "")
        year = paper.get("year", "")
        source = paper.get("source", "")
        url = paper.get("source_url", "")
        score = paper.get("relevance_score", "")
        abstract = _compact(paper.get("abstract", ""), limit=550)
        lines.extend(
            [
                f"### {idx}. {title}",
                f"- 年份/来源：{year} / {source}",
                f"- venue / target_venue：{venue} / {target}",
                f"- relevance_score：{score}",
                f"- URL：{url}",
                f"- 摘要线索：{abstract or '无摘要'}",
                "",
            ]
        )

    lines.extend(["## 4. 主题聚类"])
    keyword_groups: dict[str, list[str]] = defaultdict(list)
    for paper in selected:
        keywords = paper.get("matched_keywords", []) or ["unclassified"]
        title = str(paper.get("title", "") or "")
        for keyword in keywords[:4]:
            keyword_groups[str(keyword)].append(title)
    if keyword_groups:
        for keyword, titles in sorted(keyword_groups.items(), key=lambda item: (-len(item[1]), item[0]))[:12]:
            lines.append(f"- {keyword}: {len(titles)} 篇；代表论文：{'; '.join(titles[:3])}")
    else:
        lines.append("- 采集结果中没有稳定关键词聚类。")

    lines.extend(["", "## 5. 交叉方向观察"])
    domains = set(plan.get("domains", []) if isinstance(plan.get("domains", []), list) else [])
    if {"ai", "formal_methods"}.issubset(domains):
        lines.append(
            "- 当前主题被识别为 AI 与形式化方法交叉方向，应同时保留 ML/AI venue 和 PL/FM/SE venue 的候选论文。"
        )
    lines.append(
        "- 该自动报告基于题名、摘要和元数据生成；强结论、定量比较和方法归因需要进一步下载/ingest PDF 后用证据检索验证。"
    )

    lines.extend(["", "## 6. 可能遗漏与 Google Scholar 补查链接"])
    scholar_urls = plan.get("scholar_followup_urls", [])
    if isinstance(scholar_urls, list) and scholar_urls:
        for item in scholar_urls[:12]:
            if isinstance(item, dict):
                lines.append(f"- {item.get('label', item.get('venue', 'Scholar'))}: {item.get('url', '')}")
            else:
                lines.append(f"- {item}")
    else:
        lines.append("- 暂无补查链接。")

    warnings = collection.get("warnings", [])
    if warnings:
        lines.extend(["", "采集警告："])
        for warning in warnings[:12]:
            lines.append(f"- {warning}")

    lines.extend(
        [
            "",
            "## 7. 后续精读建议",
            "- 优先下载具有 PDF URL、relevance_score 高、且同时命中 AI 与形式化方法关键词的论文。",
            "- 对要纳入综述的论文生成全文 paper card，再构建 comparison table。",
            "- 生成综述后运行 claim-level verification，避免把 broad search 命中误写成目标 venue 论文。",
        ]
    )
    return "\n".join(lines).strip() + "\n"
