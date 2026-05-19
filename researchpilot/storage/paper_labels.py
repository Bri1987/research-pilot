from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPER_LABELS_PATH = PROJECT_ROOT / "data" / "outputs" / "paper_labels.json"


def _clean_label(value: object) -> str:
    label = str(value or "").strip()
    return " ".join(label.split())


def normalize_labels(values: object) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_items = re_split_labels(values)
    elif isinstance(values, list):
        raw_items = values
    else:
        raw_items = [values]

    labels: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        label = _clean_label(item)
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels


def re_split_labels(value: str) -> list[str]:
    text = str(value or "")
    for sep in ["，", "、", ";", "|"]:
        text = text.replace(sep, ",")
    return [item.strip() for item in text.replace("\n", ",").split(",")]


def load_paper_labels(path: str | Path = PAPER_LABELS_PATH) -> dict[str, list[str]]:
    label_path = Path(path)
    if not label_path.exists():
        return {}
    try:
        data = json.loads(label_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict) and isinstance(data.get("paper_labels"), dict):
        data = data["paper_labels"]
    if not isinstance(data, dict):
        return {}

    labels: dict[str, list[str]] = {}
    for paper_id, values in data.items():
        paper_key = str(paper_id or "").strip()
        cleaned = normalize_labels(values)
        if paper_key and cleaned:
            labels[paper_key] = cleaned
    return labels


def save_paper_labels(
    labels: dict[str, list[str]],
    path: str | Path = PAPER_LABELS_PATH,
) -> None:
    label_path = Path(path)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    cleaned = {
        str(paper_id): normalize_labels(values)
        for paper_id, values in labels.items()
        if str(paper_id).strip() and normalize_labels(values)
    }
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "paper_labels": cleaned,
    }
    label_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def all_paper_labels(labels: dict[str, list[str]] | None = None) -> list[str]:
    labels = labels if labels is not None else load_paper_labels()
    values: set[str] = set()
    canonical: dict[str, str] = {}
    for label_list in labels.values():
        for label in normalize_labels(label_list):
            key = label.lower()
            values.add(key)
            canonical.setdefault(key, label)
    return [canonical[key] for key in sorted(values)]


def labels_for_paper(
    paper_id: str,
    labels: dict[str, list[str]] | None = None,
) -> list[str]:
    labels = labels if labels is not None else load_paper_labels()
    return normalize_labels(labels.get(str(paper_id), []))


def set_paper_labels(
    paper_id: str,
    label_values: object,
    labels: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    labels = dict(labels if labels is not None else load_paper_labels())
    paper_key = str(paper_id or "").strip()
    cleaned = normalize_labels(label_values)
    if not paper_key:
        return labels
    if cleaned:
        labels[paper_key] = cleaned
    elif paper_key in labels:
        del labels[paper_key]
    save_paper_labels(labels)
    return labels


def add_labels_to_papers(
    paper_ids: list[str],
    label_values: object,
    *,
    overwrite: bool = False,
    only_unlabeled: bool = False,
    labels: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    labels = dict(labels if labels is not None else load_paper_labels())
    new_labels = normalize_labels(label_values)
    if not new_labels:
        return labels
    for raw_id in paper_ids:
        paper_id = str(raw_id or "").strip()
        if not paper_id:
            continue
        current = normalize_labels(labels.get(paper_id, []))
        if only_unlabeled and current:
            continue
        labels[paper_id] = new_labels if overwrite else normalize_labels(current + new_labels)
    save_paper_labels(labels)
    return labels
