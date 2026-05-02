import pandas as pd


COMPARISON_COLUMNS = [
    "Paper ID",
    "Title",
    "Problem",
    "Method",
    "Contribution",
    "Dataset",
    "Result",
    "Limitation",
    "Future Work",
    "Relevance",
]


def build_comparison_table(paper_cards: dict[str, dict]) -> pd.DataFrame:
    if not paper_cards:
        return pd.DataFrame(columns=COMPARISON_COLUMNS)

    rows: list[dict] = []
    for paper_id, card in paper_cards.items():
        card_dict = card if isinstance(card, dict) else {}
        rows.append(
            {
                "Paper ID": paper_id,
                "Title": card_dict.get("title", "") or "",
                "Problem": card_dict.get("problem", "") or "",
                "Method": card_dict.get("method", "") or "",
                "Contribution": card_dict.get("contribution", "") or "",
                "Dataset": card_dict.get("dataset", "") or "",
                "Result": card_dict.get("result", "") or "",
                "Limitation": card_dict.get("limitation", "") or "",
                "Future Work": card_dict.get("future_work", "") or "",
                "Relevance": card_dict.get("relevance", "") or "",
            }
        )

    return pd.DataFrame(rows, columns=COMPARISON_COLUMNS)
