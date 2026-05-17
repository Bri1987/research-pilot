from __future__ import annotations

from collections import Counter
from typing import Any


STATIC_RECOMMENDATIONS: list[dict[str, Any]] = [
    {
        "name": "AWS Automated Reasoning Group",
        "type": "research_group",
        "authors": ["Byron Cook", "Leonardo de Moura", "Clark Barrett"],
        "institutions": ["Amazon Web Services"],
        "keywords": ["automated reasoning", "formal verification", "SMT", "Lean", "program verification"],
        "domains": ["formal_methods", "programming_languages", "software_engineering"],
        "reason": "工业级自动推理、SMT、Lean 与程序验证相关，适合跟踪形式化保障的软件生成方向。",
    },
    {
        "name": "Stanford Formal Methods / Automated Reasoning",
        "type": "research_group",
        "authors": ["Clark Barrett", "Alex Aiken"],
        "institutions": ["Stanford University"],
        "keywords": ["SMT", "formal methods", "program analysis", "verification"],
        "domains": ["formal_methods", "programming_languages"],
        "reason": "SMT、程序分析和形式化方法基础研究强相关。",
    },
    {
        "name": "MIT CSAIL Programming Languages and Verification",
        "type": "research_group",
        "authors": ["Adam Chlipala", "Armando Solar-Lezama"],
        "institutions": ["MIT CSAIL"],
        "keywords": ["Coq", "program synthesis", "formal verification", "programming languages"],
        "domains": ["formal_methods", "programming_languages", "ai"],
        "reason": "覆盖交互式证明、程序合成与程序语言，是 LLM+验证交叉方向的重要候选关注源。",
    },
    {
        "name": "UC Berkeley BAIR / Software + AI",
        "type": "research_group",
        "authors": ["Dawn Song", "Koushik Sen", "Ion Stoica"],
        "institutions": ["University of California, Berkeley"],
        "keywords": ["large language models", "software engineering", "program synthesis", "security"],
        "domains": ["ai", "software_engineering", "programming_languages"],
        "reason": "AI for code、程序合成、安全与软件工程方向活跃，适合跟踪 LLM 代码生成。",
    },
    {
        "name": "Carnegie Mellon Software Engineering / AI for Code",
        "type": "research_group",
        "authors": ["Claire Le Goues", "Graham Neubig"],
        "institutions": ["Carnegie Mellon University"],
        "keywords": ["AI for code", "program repair", "software engineering", "natural language processing"],
        "domains": ["ai", "software_engineering", "nlp"],
        "reason": "软件工程、程序修复、NLP/LLM for code 的交叉方向值得持续关注。",
    },
    {
        "name": "University of Pennsylvania PRECISE / PL Group",
        "type": "research_group",
        "authors": ["Mayur Naik", "Steve Zdancewic"],
        "institutions": ["University of Pennsylvania"],
        "keywords": ["program analysis", "programming languages", "formal methods", "AI for code"],
        "domains": ["formal_methods", "programming_languages", "ai"],
        "reason": "程序分析、PL 和 AI 辅助软件工程方向相关。",
    },
    {
        "name": "Oxford Automated Verification",
        "type": "research_group",
        "authors": ["Daniel Kroening"],
        "institutions": ["University of Oxford"],
        "keywords": ["model checking", "CBMC", "automated verification", "program verification"],
        "domains": ["formal_methods", "software_engineering"],
        "reason": "模型检测和程序验证方向长期活跃，可作为形式化验证侧重点关注对象。",
    },
    {
        "name": "Tsinghua KEG / Knowledge Intelligence",
        "type": "research_group",
        "authors": ["Jie Tang"],
        "institutions": ["Tsinghua University"],
        "keywords": ["knowledge graph", "academic search", "scientific intelligence", "large language models"],
        "domains": ["ai", "data_mining"],
        "reason": "科研知识图谱、学术搜索和科技情报分析与 AMiner 类功能高度相关。",
    },
]


DOMAIN_KEYWORDS = {
    "ai": ["large language model", "llm", "machine learning", "neural", "foundation model", "人工智能", "大模型"],
    "formal_methods": ["formal", "verification", "theorem proving", "model checking", "smt", "形式化", "验证", "定理证明"],
    "programming_languages": ["programming language", "program synthesis", "compiler", "type system", "程序语言", "程序合成"],
    "software_engineering": ["software engineering", "program repair", "testing", "代码生成", "软件工程"],
    "nlp": ["natural language", "language model", "nlp", "自然语言"],
    "data_mining": ["knowledge graph", "academic search", "data mining", "知识图谱", "学术搜索"],
}


def _infer_domains(text: str) -> list[str]:
    lowered = str(text or "").lower()
    domains = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            domains.append(domain)
    return domains or ["ai"]


def _existing_names(watchlist: list[dict]) -> set[str]:
    names = set()
    for item in watchlist:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip().lower()
            if name:
                names.add(name)
    return names


def _collection_author_recommendations(
    collection: dict[str, Any] | None,
    existing: set[str],
    limit: int,
) -> list[dict[str, Any]]:
    if not isinstance(collection, dict):
        return []
    papers = collection.get("papers", [])
    if not isinstance(papers, list):
        return []

    author_counter: Counter[str] = Counter()
    venues: dict[str, set[str]] = {}
    keywords: dict[str, set[str]] = {}
    for paper in papers:
        if not isinstance(paper, dict):
            continue
        venue = str(paper.get("venue") or paper.get("target_venue") or "").strip()
        matched_keywords = {str(item) for item in paper.get("matched_keywords", []) or [] if str(item).strip()}
        for author in paper.get("authors", []) or []:
            name = str(author).strip()
            if not name or name.lower() in existing:
                continue
            author_counter[name] += 1
            if venue:
                venues.setdefault(name, set()).add(venue)
            keywords.setdefault(name, set()).update(matched_keywords)

    rows = []
    for name, count in author_counter.most_common(limit):
        rows.append(
            {
                "name": name,
                "type": "professor",
                "authors": [name],
                "institutions": [],
                "keywords": sorted(keywords.get(name, set()))[:8],
                "score": 8.0 + count,
                "reason": f"最近 collection 中出现 {count} 次；相关 venue/source：{', '.join(sorted(venues.get(name, set()))[:4]) or '未记录'}。",
                "source": "latest_collection",
            }
        )
    return rows


def recommend_watchlist_items(
    *,
    topic: str = "",
    collection: dict[str, Any] | None = None,
    paper_cards: dict[str, dict] | None = None,
    watchlist: list[dict] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    watchlist = watchlist or []
    paper_cards = paper_cards or {}
    existing = _existing_names(watchlist)
    context_parts = [topic]
    if isinstance(collection, dict):
        plan = collection.get("plan", {})
        if isinstance(plan, dict):
            context_parts.extend(plan.get("domains", []) or [])
            context_parts.extend(plan.get("keywords", []) or [])
        for paper in (collection.get("papers", []) or [])[:20]:
            if isinstance(paper, dict):
                context_parts.append(str(paper.get("title", "")))
                context_parts.append(str(paper.get("abstract", ""))[:400])
    for card in list(paper_cards.values())[:20]:
        if isinstance(card, dict):
            context_parts.extend([str(card.get("title", "")), str(card.get("relevance", "")), str(card.get("method", ""))])

    context = " ".join(context_parts)
    domains = set(_infer_domains(context))
    if "formal_methods" in domains:
        domains.update(["programming_languages", "software_engineering"])

    recommendations: list[dict[str, Any]] = []
    for item in STATIC_RECOMMENDATIONS:
        if str(item["name"]).lower() in existing:
            continue
        item_domains = set(item.get("domains", []))
        overlap = domains.intersection(item_domains)
        if not overlap:
            continue
        score = 10.0 + 2.0 * len(overlap)
        keyword_hits = [
            keyword
            for keyword in item.get("keywords", [])
            if str(keyword).lower() in context.lower()
        ]
        score += min(4, len(keyword_hits))
        recommendations.append(
            {
                **item,
                "score": score,
                "matched_domains": sorted(overlap),
                "matched_keywords": keyword_hits[:6],
                "source": "seeded_expert_graph",
            }
        )

    recommendations.extend(_collection_author_recommendations(collection, existing, limit=limit))
    recommendations.sort(key=lambda row: (-float(row.get("score", 0.0)), str(row.get("name", ""))))
    return recommendations[:limit]


def recommendation_to_watch_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name", "")).strip(),
        "type": str(item.get("type", "custom") or "custom"),
        "authors": item.get("authors", []) if isinstance(item.get("authors"), list) else [],
        "institutions": item.get("institutions", []) if isinstance(item.get("institutions"), list) else [],
        "keywords": item.get("keywords", []) if isinstance(item.get("keywords"), list) else [],
        "homepage_urls": item.get("homepage_urls", []) if isinstance(item.get("homepage_urls"), list) else [],
        "notes": str(item.get("reason", "") or ""),
    }
