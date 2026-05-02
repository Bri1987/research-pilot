from __future__ import annotations

import json
from pathlib import Path


DEFAULT_WATCHLIST_PATH = "data/outputs/watchlist.json"


def _normalize_text_list(values) -> list[str]:
    if values is None:
        return []

    raw_items: list[str] = []
    if isinstance(values, str):
        raw_items = values.splitlines()
    elif isinstance(values, list):
        raw_items = [str(item) for item in values]
    else:
        raw_items = [str(values)]

    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in raw_items:
        item = str(raw).strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _clean_watch_item(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError("watchlist item must be a dict.")

    name = str(item.get("name", "")).strip()
    if not name:
        raise ValueError("watchlist item name cannot be empty.")

    item_type = str(item.get("type", "")).strip() or "custom"
    notes = str(item.get("notes", "")).strip()

    return {
        "name": name,
        "type": item_type,
        "authors": _normalize_text_list(item.get("authors", [])),
        "institutions": _normalize_text_list(item.get("institutions", [])),
        "keywords": _normalize_text_list(item.get("keywords", [])),
        "notes": notes,
    }


def load_watchlist(path: str = DEFAULT_WATCHLIST_PATH) -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        return []

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    cleaned_items: list[dict] = []
    for raw_item in data:
        try:
            cleaned_items.append(_clean_watch_item(raw_item))
        except Exception:
            continue
    return cleaned_items


def save_watchlist(items: list[dict], path: str = DEFAULT_WATCHLIST_PATH) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    cleaned_items = [_clean_watch_item(item) for item in items]
    file_path.write_text(
        json.dumps(cleaned_items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_watch_item(item: dict, path: str = DEFAULT_WATCHLIST_PATH) -> list[dict]:
    items = load_watchlist(path=path)
    items.append(_clean_watch_item(item))
    save_watchlist(items, path=path)
    return items


def delete_watch_item(index: int, path: str = DEFAULT_WATCHLIST_PATH) -> list[dict]:
    items = load_watchlist(path=path)
    if index < 0 or index >= len(items):
        raise IndexError("watchlist index out of range.")

    del items[index]
    save_watchlist(items, path=path)
    return items
