from __future__ import annotations

import json

from researchpilot.llm.openai_client import chat_completion
from researchpilot.watchlist.watchlist_ranker import rank_papers_by_watchlist


def summarize_watchlist_trends(
    papers: list[dict],
    watchlist: list[dict],
    topic: str | None = None,
    max_papers: int = 8,
) -> str:
    if not watchlist:
        return "无法生成关注趋势总结：当前 watchlist 为空。"

    ranked = rank_papers_by_watchlist(papers, watchlist, prioritize=True)
    matched = [paper for paper in ranked if float(paper.get("watchlist_score", 0.0)) > 0]
    if not matched:
        return "当前搜索结果中没有明显匹配 watchlist 的论文。"

    limit = max(1, int(max_papers))
    top_matched = matched[:limit]

    paper_payload: list[dict] = []
    for paper in top_matched:
        paper_payload.append(
            {
                "title": paper.get("title", ""),
                "authors": paper.get("authors", []),
                "summary": paper.get("summary", ""),
                "watchlist_score": float(paper.get("watchlist_score", 0.0)),
                "watchlist_reasons": paper.get("watchlist_reasons", []),
            }
        )

    watchlist_payload: list[dict] = []
    for item in watchlist:
        watchlist_payload.append(
            {
                "name": item.get("name", ""),
                "type": item.get("type", ""),
                "authors": item.get("authors", []),
                "institutions": item.get("institutions", []),
                "keywords": item.get("keywords", []),
                "notes": item.get("notes", ""),
            }
        )

    topic_text = (topic or "").strip() or "未指定主题"
    watchlist_json = json.dumps(watchlist_payload, ensure_ascii=False, indent=2)
    papers_json = json.dumps(paper_payload, ensure_ascii=False, indent=2)

    system_prompt = (
        "你是严谨的科研情报助手。"
        "请仅基于用户提供的 watchlist 和论文结果总结趋势。"
        "不要编造搜索结果中不存在的论文或结论。"
        "输出中文 Markdown。"
    )
    user_prompt = (
        f"当前 topic：{topic_text}\n\n"
        f"Watchlist：\n{watchlist_json}\n\n"
        f"Top Matched Papers：\n{papers_json}\n\n"
        "请严格按以下结构输出：\n\n"
        "# Watchlist Trend Summary\n\n"
        "## 1. 关注对象匹配概况\n"
        "## 2. 最近相关论文主题\n"
        "## 3. 推荐优先阅读的论文\n"
        "## 4. 与当前 topic 的关系\n"
        "## 5. 后续跟踪建议\n"
    )

    result = chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return result.strip()
