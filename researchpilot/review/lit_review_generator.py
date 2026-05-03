import json

from researchpilot.llm.openai_client import chat_completion


def generate_literature_review(
    topic: str,
    paper_cards: dict[str, dict],
) -> str:
    if not paper_cards:
        return "无法生成综述：当前没有可用的 paper cards。"

    cards_payload: list[dict] = []
    for paper_id, card in paper_cards.items():
        if isinstance(card, dict):
            cards_payload.append(
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

    topic_text = (topic or "").strip() or "未指定主题"
    cards_json = json.dumps(cards_payload, ensure_ascii=False, indent=2)

    system_prompt = (
        "你是严谨的科研综述助手。"
        "你只能基于用户提供的 paper cards 写作，不得编造任何信息。"
        "输出必须为中文 Markdown。"
        "请在每个关键结论后标注来源，格式为“（来源：paper_id）”或“（来源：title）”。"
        "请使用保守措辞，避免 paper cards 难以直接支持的强表述。"
        "若没有明确证据，请使用“是一个研究问题”“在相关研究中被讨论”“在某些应用场景中具有意义”等表述。"
        "避免使用“长期存在且重要”“被广泛证明”“完全解决”“显著优于所有方法”等强断言。"
    )
    user_prompt = (
        f"研究主题：{topic_text}\n\n"
        f"可用 paper cards：\n{cards_json}\n\n"
        "请严格按以下结构输出，不要改变标题层级：\n"
        f"# 文献综述：{topic_text}\n\n"
        "## 1. 研究背景\n\n"
        "## 2. 现有方法分类\n\n"
        "## 3. 代表性工作比较\n\n"
        "## 4. 当前局限\n\n"
        "## 5. Research Gaps\n\n"
        "## 6. Future Directions\n\n"
        "要求：不要编造 paper cards 中不存在的信息；对背景判断尽量使用保守措辞。"
    )

    return chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
