import json

from researchpilot.llm.openai_client import chat_completion


_CARD_FIELDS = [
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


def _get_chunk_value(chunk, key: str, default=None):
    if isinstance(chunk, dict):
        return chunk.get(key, default)
    return getattr(chunk, key, default)


def _extract_first_json_object(text: str) -> str | None:
    start = None
    depth = 0
    in_string = False
    escaped = False

    for idx, ch in enumerate(text):
        if escaped:
            escaped = False
            continue

        if ch == "\\" and in_string:
            escaped = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            if start is None:
                start = idx
                depth = 1
            else:
                depth += 1
        elif ch == "}" and start is not None:
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return None


def _normalize_card(parsed: dict, paper_id: str) -> dict:
    card: dict = {}
    for field in _CARD_FIELDS:
        if field == "paper_id":
            value = parsed.get(field, paper_id)
            card[field] = str(value) if value is not None else paper_id
        else:
            value = parsed.get(field, "")
            card[field] = str(value) if value is not None else ""
    return card


def generate_paper_card(
    paper_id: str,
    chunks: list,
    max_chunks: int = 10,
) -> dict:
    if not chunks:
        return {
            "paper_id": paper_id,
            "error": "No chunks found for this paper.",
        }

    selected_chunks = chunks[:max_chunks]
    evidence_parts: list[str] = []
    for idx, chunk in enumerate(selected_chunks, start=1):
        chunk_paper_id = _get_chunk_value(chunk, "paper_id", paper_id)
        page = _get_chunk_value(chunk, "page", "")
        text = (_get_chunk_value(chunk, "text", "") or "").strip()
        evidence_parts.append(
            f"[C{idx}] paper_id={chunk_paper_id}, page={page}\n{text}"
        )
    evidence_text = "\n\n".join(evidence_parts)

    system_prompt = (
        "你是严谨的科研论文分析助手。"
        "请仅根据提供的论文片段生成论文卡片。"
        "输出必须是严格 JSON 对象，不要使用 Markdown code fence，不要输出额外解释。"
        "输出语言为中文。"
    )
    user_prompt = (
        f"请基于以下片段为论文生成结构化卡片。\n"
        f"paper_id: {paper_id}\n\n"
        f"片段：\n{evidence_text}\n\n"
        "请严格输出以下 JSON 字段：\n"
        "{\n"
        '  "paper_id": "...",\n'
        '  "title": "...",\n'
        '  "problem": "...",\n'
        '  "method": "...",\n'
        '  "contribution": "...",\n'
        '  "dataset": "...",\n'
        '  "result": "...",\n'
        '  "limitation": "...",\n'
        '  "future_work": "...",\n'
        '  "relevance": "..."\n'
        "}"
    )

    raw_output = chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    try:
        parsed = json.loads(raw_output)
        if not isinstance(parsed, dict):
            raise ValueError("Parsed JSON is not an object.")
        return _normalize_card(parsed, paper_id)
    except Exception as first_exc:
        try:
            json_text = _extract_first_json_object(raw_output)
            if not json_text:
                raise ValueError("No JSON object found in model output.")
            parsed = json.loads(json_text)
            if not isinstance(parsed, dict):
                raise ValueError("Extracted JSON is not an object.")
            return _normalize_card(parsed, paper_id)
        except Exception as second_exc:
            return {
                "paper_id": paper_id,
                "raw": raw_output,
                "parse_error": f"{first_exc}; {second_exc}",
            }
