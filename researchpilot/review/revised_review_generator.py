import json

from researchpilot.llm.openai_client import chat_completion


def _build_verification_summary(claim_verification: list[dict]) -> list[dict]:
    summary: list[dict] = []
    for idx, item in enumerate(claim_verification, start=1):
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

        summary.append(
            {
                "idx": idx,
                "claim": str(item.get("claim", "")),
                "status": str(item.get("status", "")),
                "reason": str(item.get("reason", "")),
                "suggested_rewrite": str(item.get("suggested_rewrite", "")),
                "best_evidence": item.get("best_evidence", []),
                "evidence_summary": evidence_summary,
            }
        )
    return summary


def generate_revised_literature_review(
    original_review: str,
    claim_verification: list[dict],
) -> str:
    if not original_review or not original_review.strip():
        return "无法生成修订版综述：原始综述为空。"
    if not claim_verification:
        return "无法生成修订版综述：尚未完成 claim-level citation verification。"

    verification_json = json.dumps(
        _build_verification_summary(claim_verification),
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = (
        "你是严谨的科研写作助手。"
        "请根据原始综述与引用核验结果生成修订版文献综述。"
        "禁止引入核验结果或证据之外的新事实。"
        "输出中文 Markdown。"
    )
    user_prompt = (
        "请根据以下信息生成修订版文献综述。\n\n"
        "重写规则：\n"
        "1. supported claims 可以保留，但可润色。\n"
        "2. weakly_supported claims 必须改为更保守表述，优先使用 suggested_rewrite。\n"
        "3. unsupported claims 若有 suggested_rewrite 则采用；"
        "若 suggested_rewrite 表示“证据不足，建议删除该声明。”则删除该 claim。\n"
        "4. 不要引入 verification 或 evidence 中没有的新事实。\n"
        "5. 在合适位置标注“（已根据引用验证修订）”。\n\n"
        "结构要求（保持这些标题层级）：\n"
        "# 修订版文献综述：...\n"
        "## 1. 研究背景\n"
        "## 2. 现有方法分类\n"
        "## 3. 代表性工作比较\n"
        "## 4. 当前局限\n"
        "## 5. Research Gaps\n"
        "## 6. Future Directions\n\n"
        f"原始综述：\n{original_review}\n\n"
        f"Claim Verification Results（摘要）：\n{verification_json}\n"
    )

    try:
        result = chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        return result.strip()
    except Exception as exc:
        return f"无法生成修订版综述：{exc}"
