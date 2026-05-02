from researchpilot.llm.openai_client import chat_completion


def format_evidence(evidence: list[dict]) -> str:
    if not evidence:
        return "（无可用证据）"

    lines: list[str] = []
    for idx, item in enumerate(evidence, start=1):
        paper_id = item.get("paper_id", "")
        page = item.get("page", "")
        score = float(item.get("score", 0.0))
        text = (item.get("text", "") or "").strip()

        lines.append(f"[E{idx}] paper_id={paper_id}, page={page}, score={score:.4f}")
        lines.append(text if text else "(empty text)")
        lines.append("")

    return "\n".join(lines).strip()


def generate_answer_with_citations(
    question: str,
    evidence: list[dict],
) -> str:
    evidence_text = format_evidence(evidence)

    system_prompt = (
        "你是严谨的 AI 科研助手。\n"
        "你只能使用给定 evidence 回答，不得使用外部知识或猜测。\n"
        "回答必须使用中文。\n"
        "关键结论必须附上引用标记，如 [E1]、[E2]。\n"
        "如果 evidence 不足以支持回答，必须明确写出“证据不足”。\n"
        "不要编造引用，不要引用不存在的证据编号。"
    )

    user_prompt = (
        f"问题：{question}\n\n"
        f"可用证据：\n{evidence_text}\n\n"
        "请基于以上证据给出回答，并在关键结论处标注引用。"
    )

    return chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
