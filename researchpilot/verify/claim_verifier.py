import json
import re

from researchpilot.llm.openai_client import chat_completion
from researchpilot.verify.claim_rewriter import suggest_conservative_rewrite


_ALLOWED_STATUS = {"supported", "weakly_supported", "unsupported"}


def _extract_first_json_array(text: str) -> str | None:
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

        if ch == "[":
            if start is None:
                start = idx
                depth = 1
            else:
                depth += 1
        elif ch == "]" and start is not None:
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]

    return None


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


def _fallback_split_claims(text: str) -> list[str]:
    parts = re.split(r"[。\.\n]+", text)
    claims: list[str] = []
    for part in parts:
        item = part.strip()
        if len(item) < 10:
            continue
        if item.startswith("#"):
            continue
        claims.append(item)
    return claims


def extract_claims(text: str) -> list[str]:
    if not text or not text.strip():
        return []

    system_prompt = (
        "你是严谨的科研信息抽取助手。"
        "请将给定综述文本拆分为可验证的 atomic factual claims。"
        "忽略纯标题和空泛过渡句。"
        "输出必须是严格 JSON list（字符串数组），不要 markdown code fence。"
    )
    user_prompt = (
        f"请从以下文本中抽取 atomic claims：\n\n{text}\n\n"
        "仅输出 JSON list，例如：[\"claim1\", \"claim2\"]"
    )

    try:
        raw_output = chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        parsed = json.loads(raw_output)
        if not isinstance(parsed, list):
            raise ValueError("Model output is not a JSON list.")
        claims = [str(item).strip() for item in parsed if str(item).strip()]
        return [claim for claim in claims if len(claim) >= 10]
    except Exception:
        try:
            raw_output = raw_output if "raw_output" in locals() else ""
            array_text = _extract_first_json_array(raw_output)
            if not array_text:
                raise ValueError("No JSON array found.")
            parsed = json.loads(array_text)
            if not isinstance(parsed, list):
                raise ValueError("Extracted content is not a JSON list.")
            claims = [str(item).strip() for item in parsed if str(item).strip()]
            filtered = [claim for claim in claims if len(claim) >= 10]
            if filtered:
                return filtered
        except Exception:
            pass

        return _fallback_split_claims(text)


def verify_claim(claim: str, evidence: list[dict]) -> dict:
    if not evidence:
        return {
            "claim": claim,
            "status": "unsupported",
            "reason": "没有检索到相关证据。",
            "best_evidence": [],
            "evidence": [],
        }

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
        "你是严格的证据核验助手。"
        "你只能基于给定 evidence 判断 claim 是否被支持。"
        "status 只能是 supported、weakly_supported、unsupported 三者之一。"
        "输出必须是严格 JSON object，不要 markdown code fence。"
    )
    user_prompt = (
        f"Claim:\n{claim}\n\n"
        f"Evidence:\n{evidence_text}\n\n"
        "请输出：\n"
        "{\n"
        '  "claim": "...",\n'
        '  "status": "supported | weakly_supported | unsupported",\n'
        '  "reason": "...",\n'
        '  "best_evidence": ["E1", "E2"]\n'
        "}"
    )

    try:
        raw_output = chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
        parsed = json.loads(raw_output)
        if not isinstance(parsed, dict):
            raise ValueError("Model output is not a JSON object.")
    except Exception:
        try:
            raw_output = raw_output if "raw_output" in locals() else ""
            obj_text = _extract_first_json_object(raw_output)
            if not obj_text:
                raise ValueError("No JSON object found.")
            parsed = json.loads(obj_text)
            if not isinstance(parsed, dict):
                raise ValueError("Extracted JSON is not an object.")
        except Exception:
            return {
                "claim": claim,
                "status": "weakly_supported",
                "reason": raw_output if "raw_output" in locals() else "JSON parse failed.",
                "best_evidence": [],
                "evidence": evidence,
            }

    status = str(parsed.get("status", "weakly_supported")).strip()
    if status not in _ALLOWED_STATUS:
        status = "weakly_supported"

    best_evidence_raw = parsed.get("best_evidence", [])
    if isinstance(best_evidence_raw, list):
        best_evidence = [str(item) for item in best_evidence_raw]
    else:
        best_evidence = []

    return {
        "claim": str(parsed.get("claim", claim)).strip() or claim,
        "status": status,
        "reason": str(parsed.get("reason", "")).strip(),
        "best_evidence": best_evidence,
        "evidence": evidence,
    }


def verify_review_claims(
    review_text: str,
    retriever,
    top_k: int = 4,
) -> list[dict]:
    claims = extract_claims(review_text)
    claims = claims[:12]

    results: list[dict] = []
    for claim in claims:
        evidence = retriever.search(claim, top_k=top_k)
        result = verify_claim(claim, evidence)

        status = str(result.get("status", ""))
        if status in {"weakly_supported", "unsupported"}:
            result["suggested_rewrite"] = suggest_conservative_rewrite(
                claim=str(result.get("claim", claim)),
                status=status,
                reason=str(result.get("reason", "")),
                evidence=result.get("evidence", []) or [],
            )
        else:
            result["suggested_rewrite"] = ""

        results.append(result)

    return results
