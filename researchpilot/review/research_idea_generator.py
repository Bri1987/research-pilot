import json

from researchpilot.llm.openai_client import chat_completion


def _build_card_payload(paper_cards: dict[str, dict]) -> list[dict]:
    payload: list[dict] = []
    for paper_id, card in paper_cards.items():
        if not isinstance(card, dict):
            continue
        payload.append(
            {
                "paper_id": paper_id,
                "title": card.get("title", ""),
                "problem": card.get("problem", ""),
                "method": card.get("method", ""),
                "contribution": card.get("contribution", ""),
                "dataset": card.get("dataset", ""),
                "result": card.get("result", ""),
                "limitation": card.get("limitation", ""),
                "future_work": card.get("future_work", ""),
                "relevance": card.get("relevance", ""),
            }
        )
    return payload


def _build_comparison_rows(cards_payload: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for item in cards_payload:
        rows.append(
            {
                "Paper ID": item.get("paper_id", ""),
                "Title": item.get("title", ""),
                "Problem": item.get("problem", ""),
                "Method": item.get("method", ""),
                "Contribution": item.get("contribution", ""),
                "Dataset": item.get("dataset", ""),
                "Result": item.get("result", ""),
                "Limitation": item.get("limitation", ""),
                "Future Work": item.get("future_work", ""),
                "Relevance": item.get("relevance", ""),
            }
        )
    return rows


def _build_claim_verification_summary(
    claim_verification: list[dict] | None,
) -> dict:
    if not claim_verification:
        return {
            "available": False,
            "counts": {
                "supported": 0,
                "weakly_supported": 0,
                "unsupported": 0,
            },
            "weak_or_unsupported_claims": [],
        }

    supported = 0
    weakly_supported = 0
    unsupported = 0
    weak_items: list[dict] = []

    for idx, item in enumerate(claim_verification, start=1):
        status = str(item.get("status", "")).strip()
        if status == "supported":
            supported += 1
        elif status == "weakly_supported":
            weakly_supported += 1
        elif status == "unsupported":
            unsupported += 1

        if status not in {"weakly_supported", "unsupported"}:
            continue

        evidence_items = item.get("evidence", []) or []
        evidence_summary: list[dict] = []
        for ev in evidence_items[:2]:
            evidence_summary.append(
                {
                    "paper_id": ev.get("paper_id", ""),
                    "page": ev.get("page", ""),
                    "score": float(ev.get("score", 0.0)),
                    "text_preview": str(ev.get("text", "")).strip()[:180],
                }
            )

        weak_items.append(
            {
                "idx": idx,
                "status": status,
                "claim": str(item.get("claim", "")),
                "reason": str(item.get("reason", "")),
                "suggested_rewrite": str(item.get("suggested_rewrite", "")),
                "best_evidence": item.get("best_evidence", []),
                "evidence_summary": evidence_summary,
            }
        )

    return {
        "available": True,
        "counts": {
            "supported": supported,
            "weakly_supported": weakly_supported,
            "unsupported": unsupported,
        },
        "weak_or_unsupported_claims": weak_items,
    }


def generate_research_ideas(
    topic: str | None,
    paper_cards: dict[str, dict],
    literature_review: str | None,
    revised_literature_review: str | None,
    claim_verification: list[dict] | None,
    num_ideas: int = 5,
) -> str:
    if not paper_cards:
        return "无法生成研究想法：当前没有可用的 paper cards。"

    idea_count = max(1, min(int(num_ideas), 8))
    topic_text = (topic or "").strip() or "未指定主题"
    original_review_text = (literature_review or "").strip()
    revised_review_text = (revised_literature_review or "").strip()

    cards_payload = _build_card_payload(paper_cards)
    cards_json = json.dumps(
        cards_payload,
        ensure_ascii=False,
        indent=2,
    )
    comparison_rows_json = json.dumps(
        _build_comparison_rows(cards_payload),
        ensure_ascii=False,
        indent=2,
    )
    verification_json = json.dumps(
        _build_claim_verification_summary(claim_verification),
        ensure_ascii=False,
        indent=2,
    )
    availability_notes = {
        "has_original_review": bool(original_review_text),
        "has_revised_review": bool(revised_review_text),
        "has_claim_verification": bool(claim_verification),
    }
    availability_json = json.dumps(availability_notes, ensure_ascii=False, indent=2)

    system_prompt = (
        "你是严谨的科研创新助手。"
        "请基于用户提供的材料提出未来研究 ideas。"
        "不得编造 paper cards、综述、引用核验中不存在的现有工作结论。"
        "输出中文 Markdown，不要输出代码块。"
    )

    user_prompt = (
        f"研究主题：{topic_text}\n\n"
        f"可用信息状态：\n{availability_json}\n\n"
        f"Paper Cards：\n{cards_json}\n\n"
        f"Comparison Table（由 paper cards 汇总）：\n{comparison_rows_json}\n\n"
        f"Original Literature Review：\n{original_review_text or '（暂无）'}\n\n"
        f"Revised Literature Review：\n{revised_review_text or '（暂无）'}\n\n"
        f"Claim Verification Summary（包含 weakly_supported/unsupported 与 suggested rewrites）：\n"
        f"{verification_json}\n\n"
        "请基于上述材料生成未来研究 ideas，要求：\n"
        f"1. 生成 {idea_count} 个 ideas。\n"
        "2. 每个 idea 要尽量具体，不要只写泛泛方向。\n"
        "3. 优先利用 limitation、research gap、weakly_supported/unsupported claim、"
        "suggested rewrite 来挖掘可行方向。\n"
        "4. 如果某些信息缺失（例如没有 revised review 或 claim verification），请在相关 idea 中明确说明"
        "证据有限并提出保守假设。\n"
        "5. 不要声称这些 ideas 一定原创；请把它们当作候选研究假设。\n"
        "6. 输出结构必须严格如下（按 idea 序号重复）：\n\n"
        "# Future Research Ideas\n\n"
        "## Idea 1: ...\n\n"
        "### Motivation\n"
        "### Research Gap\n"
        "### Proposed Method\n"
        "### Why It May Be Novel\n"
        "### Required Evidence or Experiments\n"
        "### Risks\n"
        "### Related Existing Work\n"
    )

    result = chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return result.strip()
