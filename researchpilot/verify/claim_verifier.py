import json
import re
import unicodedata

from researchpilot.llm.openai_client import chat_completion
from researchpilot.verify.claim_rewriter import suggest_conservative_rewrite


_ALLOWED_STATUS = {"supported", "weakly_supported", "unsupported"}
_ALLOWED_MODES = {"strict", "balanced", "lenient"}


def extract_source_hints(claim: str) -> list[str]:
    if not claim or not claim.strip():
        return []

    text = str(claim)
    hints: list[str] = []

    def add_hint(raw: str) -> None:
        cleaned = str(raw).strip()
        cleaned = cleaned.strip("()（）[]【】{}<>《》")
        cleaned = cleaned.strip("。.;；,，:：!?！？ ")
        if not cleaned:
            return
        hints.append(cleaned)

    bracketed_pattern = re.compile(
        r"[（(]\s*(?:来源|source)\s*[:：]\s*([^()（）]+?)\s*[)）]",
        flags=re.IGNORECASE,
    )
    for match in bracketed_pattern.finditer(text):
        add_hint(match.group(1))

    plain_pattern = re.compile(
        r"(?:来源|source)\s*[:：]\s*([^\n。；;]+)",
        flags=re.IGNORECASE,
    )
    for match in plain_pattern.finditer(text):
        add_hint(match.group(1))

    deduped: list[str] = []
    seen: set[str] = set()
    for hint in hints:
        key = hint.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hint)
    return deduped


def normalize_text_for_match(text: str) -> str:
    raw = str(text or "").lower()
    chars: list[str] = []
    for ch in raw:
        if ch.isspace():
            chars.append(" ")
            continue
        if unicodedata.category(ch).startswith("P"):
            continue
        chars.append(ch)
    normalized = "".join(chars)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _chunk_field(chunk, field: str, default=""):
    if isinstance(chunk, dict):
        return chunk.get(field, default)
    return getattr(chunk, field, default)


def _dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _strip_source_annotations(text: str) -> str:
    cleaned = str(text or "")
    cleaned = re.sub(
        r"[（(]\s*(?:来源|source)\s*[:：]\s*([^()（）]+?)\s*[)）]",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"(?:来源|source)\s*[:：]\s*([^\n。；;]+)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.strip("。.;；,， ")


_SOURCE_GENERIC_TOKENS = {
    "program",
    "alignment",
    "equivalence",
    "checking",
    "automata",
    "for",
    "of",
    "the",
    "a",
    "an",
    "and",
    "in",
    "on",
    "to",
    "with",
    "by",
}


def _tokenize_for_source_match(text: str) -> set[str]:
    if not text:
        return set()
    normalized = normalize_text_for_match(text)
    tokens = re.findall(r"[a-z0-9\u4e00-\u9fff]+", normalized)
    return {tok for tok in tokens if tok}


def _is_long_enough_for_contains(normalized_text: str, tokens: set[str]) -> bool:
    return len(normalized_text) >= 18 or len(tokens) >= 4


def _source_key_tokens(tokens: set[str]) -> set[str]:
    return {tok for tok in tokens if tok not in _SOURCE_GENERIC_TOKENS}


def build_source_index(
    chunks: list,
    paper_cards: dict[str, dict] | None = None,
) -> list[dict]:
    records_map: dict[str, dict] = {}

    def ensure_record(paper_id: str) -> dict:
        if paper_id not in records_map:
            records_map[paper_id] = {
                "paper_id": paper_id,
                "title": "",
                "aliases": [],
            }
        return records_map[paper_id]

    if isinstance(paper_cards, dict):
        for raw_paper_id, card in paper_cards.items():
            paper_id = str(raw_paper_id or "").strip()
            if not paper_id:
                continue
            record = ensure_record(paper_id)
            title = ""
            if isinstance(card, dict):
                title = str(card.get("title", "") or "").strip()
            if title:
                record["title"] = title
                record["aliases"].append(title)
            record["aliases"].append(paper_id)

    for chunk in chunks or []:
        raw_paper_id = str(_chunk_field(chunk, "paper_id", "") or "").strip()
        raw_title = str(_chunk_field(chunk, "title", "") or "").strip()
        if not raw_paper_id and not raw_title:
            continue

        paper_id = raw_paper_id or raw_title
        record = ensure_record(paper_id)
        if raw_title and not str(record.get("title", "")).strip():
            record["title"] = raw_title
        if raw_title:
            record["aliases"].append(raw_title)
        if paper_id:
            record["aliases"].append(paper_id)

    records: list[dict] = []
    for paper_id, record in records_map.items():
        title = str(record.get("title", "") or "").strip()
        aliases = _dedupe_strings(
            [str(item) for item in record.get("aliases", []) if str(item).strip()]
        )
        if title:
            aliases = _dedupe_strings([title] + aliases)
        aliases = _dedupe_strings([paper_id] + aliases)
        records.append(
            {
                "paper_id": paper_id,
                "title": title,
                "aliases": aliases,
            }
        )
    return records


def _score_source_candidate(hint_norm: str, hint_tokens: set[str], record: dict) -> float:
    paper_id = str(record.get("paper_id", "") or "")
    title = str(record.get("title", "") or "")
    aliases = [str(item) for item in record.get("aliases", []) if str(item).strip()]

    paper_id_norm = normalize_text_for_match(paper_id)
    title_norm = normalize_text_for_match(title)
    alias_norms = [normalize_text_for_match(alias) for alias in aliases]
    alias_norms = [alias for alias in alias_norms if alias]

    key_tokens = _source_key_tokens(hint_tokens)

    # Exact equality is the highest confidence.
    if title_norm and hint_norm == title_norm:
        return 1.0
    if paper_id_norm and hint_norm == paper_id_norm:
        return 0.99
    if hint_norm in alias_norms:
        return 0.98

    # Precision-first contains match: require sufficiently long strings and key tokens.
    if key_tokens:
        if title_norm:
            title_tokens = _tokenize_for_source_match(title_norm)
            if key_tokens.issubset(title_tokens):
                if (
                    hint_norm in title_norm
                    and _is_long_enough_for_contains(hint_norm, hint_tokens)
                ):
                    return 0.95
                if (
                    title_norm in hint_norm
                    and _is_long_enough_for_contains(title_norm, title_tokens)
                ):
                    return 0.94
        if paper_id_norm:
            paper_id_tokens = _tokenize_for_source_match(paper_id_norm)
            if key_tokens.issubset(paper_id_tokens):
                if (
                    hint_norm in paper_id_norm
                    and _is_long_enough_for_contains(hint_norm, hint_tokens)
                ):
                    return 0.93
                if (
                    paper_id_norm in hint_norm
                    and _is_long_enough_for_contains(paper_id_norm, paper_id_tokens)
                ):
                    return 0.92

    # Strict token similarity fallback: high threshold + key-token coverage.
    best_token_score = 0.0
    if key_tokens:
        for candidate_norm in [title_norm, paper_id_norm, *alias_norms]:
            if not candidate_norm:
                continue
            candidate_tokens = _tokenize_for_source_match(candidate_norm)
            if not candidate_tokens:
                continue
            if not key_tokens.issubset(candidate_tokens):
                continue
            union = hint_tokens | candidate_tokens
            if not union:
                continue
            jaccard = len(hint_tokens & candidate_tokens) / len(union)
            if jaccard >= 0.85:
                best_token_score = max(best_token_score, float(jaccard))

    return best_token_score


def _match_source_hints_with_meta(
    source_hints: list[str],
    chunks: list,
    paper_cards: dict[str, dict] | None = None,
) -> dict:
    normalized_hints = [normalize_text_for_match(hint) for hint in source_hints if hint]
    normalized_hints = [hint for hint in normalized_hints if hint]
    if not normalized_hints:
        return {
            "matched_source_paper_ids": [],
            "matched_source_titles": [],
            "source_match_failed": bool(source_hints),
            "source_match_confidence": None,
        }

    source_records = build_source_index(chunks=chunks, paper_cards=paper_cards)
    if not source_records:
        return {
            "matched_source_paper_ids": [],
            "matched_source_titles": [],
            "source_match_failed": True,
            "source_match_confidence": None,
        }

    matched_ids: list[str] = []
    matched_titles: list[str] = []
    confidences: list[float] = []
    seen_ids: set[str] = set()

    for hint_norm in normalized_hints:
        hint_tokens = _tokenize_for_source_match(hint_norm)
        key_tokens = _source_key_tokens(hint_tokens)
        # Generic-token-only hint is too ambiguous for precision-first matching.
        if not key_tokens:
            return {
                "matched_source_paper_ids": [],
                "matched_source_titles": [],
                "source_match_failed": True,
                "source_match_confidence": None,
            }

        scored_candidates: list[tuple[float, dict]] = []
        for record in source_records:
            score = _score_source_candidate(hint_norm, hint_tokens, record)
            if score > 0:
                scored_candidates.append((score, record))

        if not scored_candidates:
            return {
                "matched_source_paper_ids": [],
                "matched_source_titles": [],
                "source_match_failed": True,
                "source_match_confidence": None,
            }

        scored_candidates.sort(
            key=lambda item: (
                -item[0],
                str(item[1].get("paper_id", "")),
            )
        )
        best_score, best_record = scored_candidates[0]
        if best_score < 0.85:
            return {
                "matched_source_paper_ids": [],
                "matched_source_titles": [],
                "source_match_failed": True,
                "source_match_confidence": None,
            }

        if len(scored_candidates) > 1:
            second_score = scored_candidates[1][0]
            if second_score >= 0.85 and abs(best_score - second_score) <= 0.03:
                # Ambiguous near-tie: do not force source matching.
                return {
                    "matched_source_paper_ids": [],
                    "matched_source_titles": [],
                    "source_match_failed": True,
                    "source_match_confidence": None,
                }

        paper_id = str(best_record.get("paper_id", "") or "")
        title = str(best_record.get("title", "") or "")
        if paper_id and paper_id not in seen_ids:
            seen_ids.add(paper_id)
            matched_ids.append(paper_id)
            matched_titles.append(title)
        confidences.append(float(best_score))

    return {
        "matched_source_paper_ids": matched_ids,
        "matched_source_titles": matched_titles,
        "source_match_failed": bool(normalized_hints) and not bool(matched_ids),
        "source_match_confidence": min(confidences) if confidences else None,
    }


def match_source_hint_to_paper_ids(
    source_hints: list[str],
    chunks: list,
    paper_cards: dict[str, dict] | None = None,
) -> list[str]:
    meta = _match_source_hints_with_meta(
        source_hints=source_hints,
        chunks=chunks,
        paper_cards=paper_cards,
    )
    return list(meta.get("matched_source_paper_ids", []))


def select_diverse_evidence(
    candidates: list[dict],
    top_k: int = 5,
    max_per_paper: int = 2,
) -> list[dict]:
    if top_k <= 0 or not candidates:
        return []

    per_paper_limit = max(1, int(max_per_paper))
    selected: list[dict] = []
    selected_chunk_ids: set[str] = set()
    per_paper_count: dict[str, int] = {}

    # Round 1: prioritize source coverage (new paper_id first).
    for item in candidates:
        if len(selected) >= top_k:
            break
        chunk_id = str(item.get("chunk_id", ""))
        paper_id = str(item.get("paper_id", ""))
        if chunk_id and chunk_id in selected_chunk_ids:
            continue
        if paper_id in per_paper_count:
            continue
        selected.append(item)
        if chunk_id:
            selected_chunk_ids.add(chunk_id)
        per_paper_count[paper_id] = per_paper_count.get(paper_id, 0) + 1

    # Round 2: fill by rank order with per-paper cap.
    for item in candidates:
        if len(selected) >= top_k:
            break
        chunk_id = str(item.get("chunk_id", ""))
        paper_id = str(item.get("paper_id", ""))
        if chunk_id and chunk_id in selected_chunk_ids:
            continue
        if per_paper_count.get(paper_id, 0) >= per_paper_limit:
            continue
        selected.append(item)
        if chunk_id:
            selected_chunk_ids.add(chunk_id)
        per_paper_count[paper_id] = per_paper_count.get(paper_id, 0) + 1

    # Round 3: if still insufficient, fill remaining by rank order.
    if len(selected) < top_k:
        for item in candidates:
            if len(selected) >= top_k:
                break
            chunk_id = str(item.get("chunk_id", ""))
            if chunk_id and chunk_id in selected_chunk_ids:
                continue
            selected.append(item)
            if chunk_id:
                selected_chunk_ids.add(chunk_id)

    return selected[:top_k]


def _tokenize_for_overlap(text: str) -> set[str]:
    if not text:
        return set()
    tokens = re.findall(r"[A-Za-z0-9_\u4e00-\u9fff]+", str(text).lower())
    return {tok for tok in tokens if len(tok) >= 2}


def _chunk_to_evidence_dict(chunk, score: float = 0.0) -> dict:
    chunk_id = str(_chunk_field(chunk, "chunk_id", "") or "")
    paper_id = str(_chunk_field(chunk, "paper_id", "") or "")
    page = _chunk_field(chunk, "page", "")
    text = str(_chunk_field(chunk, "text", "") or "")
    return {
        "rank": 0,
        "score": float(score),
        "chunk_id": chunk_id,
        "paper_id": paper_id,
        "page": page,
        "text": text,
    }


def _finalize_evidence(evidence: list[dict], top_k: int) -> list[dict]:
    if not evidence or top_k <= 0:
        return []

    finalized: list[dict] = []
    seen_chunk_ids: set[str] = set()
    for item in evidence:
        chunk_id = str(item.get("chunk_id", "") or "")
        if chunk_id and chunk_id in seen_chunk_ids:
            continue
        if chunk_id:
            seen_chunk_ids.add(chunk_id)
        normalized = {
            "rank": 0,
            "score": float(item.get("score", 0.0)),
            "chunk_id": chunk_id,
            "paper_id": str(item.get("paper_id", "") or ""),
            "page": item.get("page", ""),
            "text": str(item.get("text", "") or ""),
        }
        finalized.append(normalized)
        if len(finalized) >= top_k:
            break

    for idx, item in enumerate(finalized, start=1):
        item["rank"] = idx

    return finalized


def _rank_source_chunks_by_keyword_overlap(
    claim: str,
    source_chunks: list,
    exclude_chunk_ids: set[str],
) -> list[dict]:
    claim_tokens = _tokenize_for_overlap(claim)
    scored: list[tuple[float, dict]] = []

    for chunk in source_chunks:
        ev = _chunk_to_evidence_dict(chunk)
        chunk_id = str(ev.get("chunk_id", ""))
        if chunk_id and chunk_id in exclude_chunk_ids:
            continue
        chunk_tokens = _tokenize_for_overlap(str(ev.get("text", "")))
        if claim_tokens and chunk_tokens:
            overlap = len(claim_tokens & chunk_tokens)
            score = overlap / max(len(claim_tokens), 1)
        else:
            score = 0.0
        ev["score"] = float(score)
        scored.append((score, ev))

    scored.sort(
        key=lambda item: (
            -item[0],
            str(item[1].get("paper_id", "")),
            str(item[1].get("chunk_id", "")),
        )
    )
    return [item[1] for item in scored]


def source_aware_evidence_search(
    claim: str,
    retriever,
    top_k: int = 5,
    diversify_evidence: bool = True,
    max_per_paper: int = 2,
    source_first: bool = True,
    explicit_source_hints: list[str] | None = None,
    source_only_when_available: bool = True,
    paper_cards: dict[str, dict] | None = None,
) -> tuple[list[dict], dict]:
    safe_top_k = max(1, int(top_k))
    safe_max_per_paper = max(1, int(max_per_paper))
    use_diverse = bool(diversify_evidence)
    use_source_first = bool(source_first)
    use_source_only = bool(source_only_when_available)

    source_hints = (
        explicit_source_hints
        if explicit_source_hints is not None
        else extract_source_hints(claim)
    )
    source_hints = _dedupe_strings([str(item) for item in source_hints])

    retriever_chunks = getattr(retriever, "chunks", None)
    if not isinstance(retriever_chunks, list):
        retriever_chunks = []

    source_match_meta = _match_source_hints_with_meta(
        source_hints=source_hints,
        chunks=retriever_chunks,
        paper_cards=paper_cards,
    )
    matched_source_paper_ids = list(
        source_match_meta.get("matched_source_paper_ids", [])
    )
    matched_source_titles = list(source_match_meta.get("matched_source_titles", []))
    source_match_failed = bool(source_match_meta.get("source_match_failed", False))
    source_match_confidence = source_match_meta.get("source_match_confidence")
    single_source_mode = len(matched_source_paper_ids) == 1

    meta = {
        "source_hints": source_hints,
        "matched_source_paper_ids": matched_source_paper_ids,
        "matched_source_titles": matched_source_titles,
        "source_match_failed": source_match_failed,
        "source_match_confidence": source_match_confidence,
        "source_first": use_source_first,
        "source_only_when_available": use_source_only,
        "source_only_effective": bool(matched_source_paper_ids and use_source_only),
        "single_source_mode": single_source_mode,
        "diversify_evidence": use_diverse,
    }

    if matched_source_paper_ids and use_source_only:
        global_candidates = retriever.search(claim, top_k=max(safe_top_k * 10, 50))
        source_candidates = [
            item
            for item in global_candidates
            if str(item.get("paper_id", "")) in matched_source_paper_ids
        ]

        if single_source_mode:
            # Single matched source paper: ignore max_per_paper and fill from that source only.
            selected = source_candidates[:safe_top_k]
        elif use_diverse:
            selected = select_diverse_evidence(
                source_candidates,
                top_k=safe_top_k,
                max_per_paper=safe_max_per_paper,
            )
        else:
            selected = source_candidates[:safe_top_k]

        if len(selected) < safe_top_k and retriever_chunks:
            selected_chunk_ids = {
                str(item.get("chunk_id", ""))
                for item in selected
                if str(item.get("chunk_id", ""))
            }
            source_chunk_pool = [
                chunk
                for chunk in retriever_chunks
                if str(_chunk_field(chunk, "paper_id", "") or "")
                in matched_source_paper_ids
            ]
            supplements = _rank_source_chunks_by_keyword_overlap(
                claim=claim,
                source_chunks=source_chunk_pool,
                exclude_chunk_ids=selected_chunk_ids,
            )
            remaining_k = safe_top_k - len(selected)
            selected.extend(supplements[:remaining_k])

        # Enforce source-only evidence.
        selected = [
            item
            for item in selected
            if str(item.get("paper_id", "")) in matched_source_paper_ids
        ]
        if use_diverse and not single_source_mode:
            selected = select_diverse_evidence(
                selected,
                top_k=safe_top_k,
                max_per_paper=safe_max_per_paper,
            )
        evidence = _finalize_evidence(selected, safe_top_k)
        return evidence, meta

    if matched_source_paper_ids and use_source_first:
        global_candidates = retriever.search(claim, top_k=max(safe_top_k * 8, 40))
        source_candidates = [
            item
            for item in global_candidates
            if str(item.get("paper_id", "")) in matched_source_paper_ids
        ]

        if use_diverse:
            evidence = select_diverse_evidence(
                source_candidates,
                top_k=safe_top_k,
                max_per_paper=safe_max_per_paper,
            )
        else:
            evidence = source_candidates[:safe_top_k]

        if len(evidence) < safe_top_k:
            selected_chunk_ids = {
                str(item.get("chunk_id", ""))
                for item in evidence
                if str(item.get("chunk_id", ""))
            }
            remaining_candidates = [
                item
                for item in global_candidates
                if str(item.get("chunk_id", "")) not in selected_chunk_ids
            ]
            remaining_k = safe_top_k - len(evidence)
            if use_diverse:
                supplement = select_diverse_evidence(
                    remaining_candidates,
                    top_k=remaining_k,
                    max_per_paper=safe_max_per_paper,
                )
            else:
                supplement = remaining_candidates[:remaining_k]
            evidence.extend(supplement)

        return _finalize_evidence(evidence, safe_top_k), meta

    if use_diverse:
        candidates = retriever.search(claim, top_k=max(safe_top_k * 6, 30))
        evidence = select_diverse_evidence(
            candidates,
            top_k=safe_top_k,
            max_per_paper=safe_max_per_paper,
        )
        return _finalize_evidence(evidence, safe_top_k), meta

    evidence = retriever.search(claim, top_k=safe_top_k)
    return _finalize_evidence(evidence, safe_top_k), meta


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


def _fallback_split_claim_items(text: str) -> list[dict]:
    parts = re.split(r"[。\.\n]+", text)
    items: list[dict] = []
    for part in parts:
        sentence = part.strip()
        if len(sentence) < 10:
            continue
        if sentence.startswith("#"):
            continue
        source_hints = extract_source_hints(sentence)
        claim = _strip_source_annotations(sentence).strip()
        if len(claim) < 10:
            continue
        items.append(
            {
                "claim": claim,
                "source_hints": source_hints,
            }
        )
    return items


def _normalize_claim_items(payload) -> list[dict]:
    if not isinstance(payload, list):
        return []

    normalized: list[dict] = []
    for raw_item in payload:
        if not isinstance(raw_item, dict):
            continue

        claim_raw = str(raw_item.get("claim", "")).strip()
        if not claim_raw:
            continue

        claim = _strip_source_annotations(claim_raw).strip()
        if len(claim) < 10:
            continue

        raw_hints = raw_item.get("source_hints", [])
        hints: list[str]
        if isinstance(raw_hints, list):
            hints = [str(item).strip() for item in raw_hints if str(item).strip()]
        elif isinstance(raw_hints, str):
            hints = [raw_hints.strip()] if raw_hints.strip() else []
        else:
            hints = []

        hints_from_claim = extract_source_hints(claim_raw)
        source_hints = _dedupe_strings(hints + hints_from_claim)

        normalized.append(
            {
                "claim": claim,
                "source_hints": source_hints,
            }
        )

    return normalized


def extract_claim_items(text: str) -> list[dict]:
    if not text or not text.strip():
        return []

    system_prompt = (
        "你是严谨的科研信息抽取助手。"
        "请将给定综述文本拆分为可验证的 atomic factual claims。"
        "忽略纯标题和空泛过渡句。"
        "如果句子包含来源标注（如‘来源：...’或‘source: ...’），"
        "必须把来源写入 source_hints。"
        "claim 字段可以去掉来源标注本身，但 source_hints 必须保留。"
        "输出必须是严格 JSON list of objects，不要 markdown code fence。"
        "每个 object 都必须包含 claim 和 source_hints（字符串数组）。"
    )
    user_prompt = (
        f"请从以下文本中抽取 atomic claims：\n\n{text}\n\n"
        "仅输出 JSON list，例如："
        "["
        "{\"claim\": \"...\", \"source_hints\": [\"paper title\"]},"
        "{\"claim\": \"...\", \"source_hints\": []}"
        "]"
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
        items = _normalize_claim_items(parsed)
        if items:
            text_has_hints = bool(extract_source_hints(text))
            items_have_hints = any(item.get("source_hints") for item in items)
            if text_has_hints and not items_have_hints:
                return _fallback_split_claim_items(text)
            return items
    except Exception:
        pass

    try:
        raw_text = raw_output if "raw_output" in locals() else ""
        array_text = _extract_first_json_array(raw_text)
        if array_text:
            parsed = json.loads(array_text)
            items = _normalize_claim_items(parsed)
            if items:
                text_has_hints = bool(extract_source_hints(text))
                items_have_hints = any(item.get("source_hints") for item in items)
                if text_has_hints and not items_have_hints:
                    return _fallback_split_claim_items(text)
                return items
    except Exception:
        pass

    return _fallback_split_claim_items(text)


def extract_claims(text: str) -> list[str]:
    items = extract_claim_items(text)
    return [str(item.get("claim", "")).strip() for item in items if str(item.get("claim", "")).strip()]


def _normalize_verification_mode(verification_mode: str) -> str:
    mode = str(verification_mode or "").strip().lower()
    if mode not in _ALLOWED_MODES:
        return "balanced"
    return mode


def _mode_instruction(verification_mode: str) -> str:
    mode = _normalize_verification_mode(verification_mode)
    if mode == "strict":
        return (
            "严格模式（strict）："
            "只有 evidence 明确、直接、完整支持 claim 时才标记 supported；"
            "若 evidence 只支持部分内容或 claim 表述过强，标记 weakly_supported；"
            "若没有证据或存在矛盾，标记 unsupported。"
        )
    if mode == "lenient":
        return (
            "宽松模式（lenient）："
            "对 background_or_motivation_claim，若 evidence 支持核心主题相关性与应用背景，倾向标记 supported；"
            "若只能说明主题相关但无法体现核心问题或应用场景，标记 weakly_supported；"
            "对 concrete_method_or_result_claim，仍需 evidence 明确支持；"
            "对 comparative_or_universal_claim，不要过度宽松，缺少明确 evidence 时标记 weakly_supported 或 unsupported；"
            "只有明显无关、无证据或矛盾时，才标记 unsupported。"
        )
    return (
        "平衡模式（balanced）："
        "若 evidence 支持 claim 的核心意思，即使不是覆盖所有细节，也可标记 supported；"
        "对 background_or_motivation_claim，不要求逐字匹配“重要/长期存在”等措辞；"
        "对 concrete_method_or_result_claim（尤其数字、实验结果、方法组成）和 comparative_or_universal_claim，仍需更直接证据；"
        "若 claim 比 evidence 更强、范围更大或仅被部分支持，标记 weakly_supported；"
        "只有 evidence 完全无法支持 claim，或 claim 与 evidence 明显矛盾时，才标记 unsupported。"
    )


def _claim_type_instruction() -> str:
    return (
        "请先在内部判断 claim 类型（无需在最终 JSON 输出该字段）："
        "1) background_or_motivation_claim：如‘X 是重要问题/长期挑战/有重要应用/有意义’。"
        "对该类 claim，不要求 evidence 逐字出现‘重要’‘长期存在’；"
        "若 evidence 显示 X 是论文核心问题、引言/摘要重点问题，或给出 X 的应用场景，"
        "在 balanced/lenient 下可倾向 supported；"
        "若仅能说明主题相关但不能说明核心问题或应用场景，标记 weakly_supported；"
        "只有 evidence 完全无关或矛盾时标记 unsupported。"
        "2) concrete_method_or_result_claim：如方法组成、系统模块、具体数字和实验结果。"
        "该类 claim 需要更直接 evidence，不能凭常识补全数字/结果/模块。"
        "3) comparative_or_universal_claim：如‘优于所有方法’‘解决所有问题’‘完全消除幻觉’。"
        "该类 claim 即使 lenient 也应保持严格，缺少明确证据时标记 weakly_supported 或 unsupported。"
    )


def verify_claim(
    claim: str,
    evidence: list[dict],
    verification_mode: str = "balanced",
) -> dict:
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
        f"{_claim_type_instruction()}"
        f"{_mode_instruction(verification_mode)}"
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
    top_k: int = 5,
    verification_mode: str = "balanced",
    diversify_evidence: bool = True,
    max_per_paper: int = 2,
    source_first: bool = True,
    source_only_when_available: bool = True,
    paper_cards: dict[str, dict] | None = None,
) -> list[dict]:
    claim_items = extract_claim_items(review_text)
    claim_items = claim_items[:12]
    mode = _normalize_verification_mode(verification_mode)

    results: list[dict] = []
    for item in claim_items:
        claim = str(item.get("claim", "")).strip()
        if not claim:
            continue
        source_hints_from_item = _dedupe_strings(
            [str(v) for v in (item.get("source_hints", []) or [])]
        )

        evidence, retrieval_meta = source_aware_evidence_search(
            claim=claim,
            retriever=retriever,
            top_k=top_k,
            diversify_evidence=diversify_evidence,
            max_per_paper=max_per_paper,
            source_first=source_first,
            explicit_source_hints=source_hints_from_item,
            source_only_when_available=source_only_when_available,
            paper_cards=paper_cards,
        )
        result = verify_claim(
            claim,
            evidence,
            verification_mode=mode,
        )
        result["source_hints"] = source_hints_from_item
        result["evidence_retrieval_meta"] = retrieval_meta

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
