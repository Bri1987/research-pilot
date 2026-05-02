from researchpilot.llm.openai_client import chat_completion


def suggest_conservative_rewrite(
    claim: str,
    status: str,
    reason: str,
    evidence: list[dict],
) -> str:
    if status == "supported":
        return ""

    if not evidence:
        return "证据不足，建议删除该声明。"

    evidence_lines: list[str] = []
    for idx, item in enumerate(evidence, start=1):
        paper_id = item.get("paper_id", "")
        page = item.get("page", "")
        score = float(item.get("score", 0.0))
        text = (item.get("text", "") or "").strip()
        evidence_lines.append(
            f"[E{idx}] paper_id={paper_id}, page={page}, score={score:.4f}\n{text}"
        )
    evidence_text = "\n\n".join(evidence_lines)

    system_prompt = (
        "你是谨慎的科研写作助手。"
        "请仅基于给定 evidence 对 claim 提供保守改写建议。"
        "不要引入 evidence 中没有的信息。"
        "如果证据只能支持更弱说法，请改写为更保守表述。"
        "如果证据完全不支持该 claim，请输出“证据不足，建议删除该声明。”"
        "输出中文纯文本，不要 markdown code fence。"
    )
    user_prompt = (
        f"原始 claim：{claim}\n"
        f"当前状态：{status}\n"
        f"核验理由：{reason}\n\n"
        f"evidence：\n{evidence_text}\n\n"
        "请给出一句或一小段保守改写建议。"
    )

    try:
        result = chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        return result.strip()
    except Exception as exc:
        return f"无法生成改写建议：{exc}"
