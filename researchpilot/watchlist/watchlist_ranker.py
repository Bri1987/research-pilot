from __future__ import annotations


def _contains_substring(text: str, query: str) -> bool:
    if not query:
        return False
    return query.lower() in text.lower()


def _paper_institutions(paper: dict) -> list[str]:
    values = paper.get("institutions")
    if not values:
        values = paper.get("affiliations")
    if not values:
        return []

    if isinstance(values, list):
        return [str(item) for item in values]
    return [str(values)]


def score_paper_against_watch_item(paper: dict, item: dict) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    title = str(paper.get("title", "") or "")
    summary = str(paper.get("summary", "") or "")
    authors = [str(name) for name in (paper.get("authors") or [])]
    institutions = _paper_institutions(paper)

    item_authors = [str(name) for name in (item.get("authors") or [])]
    item_institutions = [str(name) for name in (item.get("institutions") or [])]
    item_keywords = [str(name) for name in (item.get("keywords") or [])]
    item_name = str(item.get("name", "") or "").strip()

    for target_author in item_authors:
        target_author = target_author.strip()
        if not target_author:
            continue
        matched = False
        for paper_author in authors:
            if _contains_substring(paper_author, target_author) or _contains_substring(
                target_author, paper_author
            ):
                matched = True
                break
        if matched:
            score += 4.0
            reasons.append(f"matched author: {target_author}")

    for target_inst in item_institutions:
        target_inst = target_inst.strip()
        if not target_inst:
            continue
        matched = False
        for paper_inst in institutions:
            if _contains_substring(paper_inst, target_inst) or _contains_substring(
                target_inst, paper_inst
            ):
                matched = True
                break
        if matched:
            score += 3.0
            reasons.append(f"matched institution: {target_inst}")

    for keyword in item_keywords:
        keyword = keyword.strip()
        if not keyword:
            continue
        if _contains_substring(title, keyword):
            score += 3.0
            reasons.append(f"matched keyword in title: {keyword}")
        if _contains_substring(summary, keyword):
            score += 1.0
            reasons.append(f"matched keyword in summary: {keyword}")

    if item_name and (_contains_substring(title, item_name) or _contains_substring(summary, item_name)):
        score += 2.0
        reasons.append(f"matched watch item name: {item_name}")

    return score, reasons


def score_paper_against_watchlist(paper: dict, watchlist: list[dict]) -> dict:
    total_score = 0.0
    all_reasons: list[str] = []
    matched_items: list[str] = []

    for item in watchlist:
        item_name = str(item.get("name", "")).strip()
        item_score, item_reasons = score_paper_against_watch_item(paper, item)
        if item_score <= 0:
            continue

        total_score += item_score
        if item_name:
            matched_items.append(item_name)
        if item_name:
            all_reasons.extend([f"[{item_name}] {reason}" for reason in item_reasons])
        else:
            all_reasons.extend(item_reasons)

    dedup_reasons: list[str] = []
    reason_seen: set[str] = set()
    for reason in all_reasons:
        if reason in reason_seen:
            continue
        reason_seen.add(reason)
        dedup_reasons.append(reason)

    dedup_items: list[str] = []
    item_seen: set[str] = set()
    for name in matched_items:
        key = name.lower()
        if key in item_seen:
            continue
        item_seen.add(key)
        dedup_items.append(name)

    return {
        "watchlist_score": float(total_score),
        "watchlist_reasons": dedup_reasons,
        "matched_watch_items": dedup_items,
    }


def rank_papers_by_watchlist(
    papers: list[dict],
    watchlist: list[dict],
    prioritize: bool = True,
) -> list[dict]:
    scored: list[dict] = []
    for idx, paper in enumerate(papers):
        row = dict(paper)
        score_data = score_paper_against_watchlist(row, watchlist)
        row.update(score_data)
        row["_original_idx"] = idx
        scored.append(row)

    if prioritize:
        scored.sort(
            key=lambda p: (-float(p.get("watchlist_score", 0.0)), p.get("_original_idx", 0)),
        )

    for item in scored:
        item.pop("_original_idx", None)
    return scored
