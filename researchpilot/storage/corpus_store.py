import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPER_CARD_CACHE_PATH = PROJECT_ROOT / "data" / "outputs" / "paper_cards_cache.json"


def load_paper_cards_cache(path: str | Path = PAPER_CARD_CACHE_PATH) -> dict[str, dict]:
    cache_path = Path(path)
    if not cache_path.exists():
        return {}

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    normalized: dict[str, dict] = {}
    for paper_id, card in data.items():
        if not isinstance(card, dict):
            continue
        normalized[str(paper_id)] = card
    return normalized


def save_paper_cards_cache(
    cards: dict[str, dict],
    path: str | Path = PAPER_CARD_CACHE_PATH,
) -> None:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(cards, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_cached_paper_card(
    paper_id: str,
    path: str | Path = PAPER_CARD_CACHE_PATH,
) -> dict | None:
    paper_key = str(paper_id or "").strip()
    if not paper_key:
        return None
    cards = load_paper_cards_cache(path=path)
    card = cards.get(paper_key)
    return card if isinstance(card, dict) else None


def set_cached_paper_card(
    paper_id: str,
    card: dict,
    path: str | Path = PAPER_CARD_CACHE_PATH,
) -> dict[str, dict]:
    paper_key = str(paper_id or "").strip()
    if not paper_key:
        return load_paper_cards_cache(path=path)

    cards = load_paper_cards_cache(path=path)
    cards[paper_key] = card if isinstance(card, dict) else {"paper_id": paper_key}
    save_paper_cards_cache(cards, path=path)
    return cards


def delete_cached_paper_card(
    paper_id: str,
    path: str | Path = PAPER_CARD_CACHE_PATH,
) -> dict[str, dict]:
    paper_key = str(paper_id or "").strip()
    cards = load_paper_cards_cache(path=path)
    if paper_key and paper_key in cards:
        del cards[paper_key]
        save_paper_cards_cache(cards, path=path)
    return cards
