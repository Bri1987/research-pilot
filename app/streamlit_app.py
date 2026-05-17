from pathlib import Path
from datetime import datetime
import html as html_lib
import json
import re
import sys

import streamlit as st

# Allow `streamlit run app/streamlit_app.py` from repo root without extra PYTHONPATH.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from researchpilot.cards.comparison_table import build_comparison_table
from researchpilot.cards.metadata_cards import CARD_FIELDS
from researchpilot.cards.metadata_cards import metadata_paper_id
from researchpilot.cards.metadata_cards import paper_card_from_metadata
from researchpilot.agent_bridge import agent_bridge_status
from researchpilot.agent_bridge import list_agent_tasks
from researchpilot.agent_bridge import queue_agent_task
from researchpilot.agent_bridge import run_agent_task
from researchpilot.config import get_config
from researchpilot.discovery.venue_collector import collect_venue_papers
from researchpilot.discovery.venue_collector import plan_venue_collection
from researchpilot.ingest.pipeline import ResearchPilotPipeline
from researchpilot.llm.openai_client import chat_completion
from researchpilot.review.venue_report import deterministic_venue_report
from researchpilot.review.review_diff import make_unified_diff
from researchpilot.search.arxiv_search import download_arxiv_paper
from researchpilot.search.arxiv_search import download_pdf_from_url
from researchpilot.search.arxiv_search import search_arxiv_papers
from researchpilot.storage.corpus_store import load_paper_cards_cache
from researchpilot.storage.corpus_store import save_paper_cards_cache
from researchpilot.storage.paper_labels import add_labels_to_papers
from researchpilot.storage.paper_labels import all_paper_labels
from researchpilot.storage.paper_labels import labels_for_paper
from researchpilot.storage.paper_labels import load_paper_labels
from researchpilot.storage.paper_labels import normalize_labels
from researchpilot.storage.paper_labels import save_paper_labels
from researchpilot.storage.paper_labels import set_paper_labels
from researchpilot.watchlist.watchlist_ranker import rank_papers_by_watchlist
from researchpilot.watchlist.recommendations import recommendation_to_watch_item
from researchpilot.watchlist.recommendations import recommend_watchlist_items
from researchpilot.watchlist.tracker import dismiss_watch_paper
from researchpilot.watchlist.tracker import get_watch_item_tracking
from researchpilot.watchlist.tracker import homepage_index_for_watch_item
from researchpilot.watchlist.tracker import load_watchlist_tracking
from researchpilot.watchlist.tracker import track_watch_item
from researchpilot.watchlist.tracker import watch_item_key
from researchpilot.watchlist.watchlist_store import add_watch_item
from researchpilot.watchlist.watchlist_store import delete_watch_item
from researchpilot.watchlist.watchlist_store import load_watchlist
from researchpilot.watchlist.watchlist_summary import summarize_watchlist_trends
from researchpilot.workspace import LAST_VENUE_COLLECTION_PATH
from researchpilot.workspace import list_workspace_reports
from researchpilot.workspace import save_workspace_report
from researchpilot.workspace import workspace_context_payload


UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="ResearchPilot",
    layout="wide",
)


def _escape_html(value: object) -> str:
    return html_lib.escape("" if value is None else str(value), quote=True)


st.html(
    """
    <style>
    :root {
        --rp-ink: #18202f;
        --rp-muted: #697386;
        --rp-soft: #f5f8fc;
        --rp-panel: rgba(255, 255, 255, 0.82);
        --rp-panel-strong: rgba(255, 255, 255, 0.94);
        --rp-line: rgba(107, 123, 148, 0.18);
        --rp-blue: #246bfe;
        --rp-cyan: #00a7b5;
        --rp-green: #1b8f68;
        --rp-amber: #b47b12;
        --rp-red: #c75353;
        --rp-shadow: 0 24px 70px rgba(37, 48, 68, 0.12);
        --rp-shadow-soft: 0 14px 34px rgba(37, 48, 68, 0.08);
        --rp-radius: 18px;
    }

    html, body, [class*="css"] {
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
            "SF Pro Display", "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif;
        color: var(--rp-ink);
    }

    .stApp {
        background:
            linear-gradient(135deg, #f8fbff 0%, #f1f8fb 35%, #f7fbf4 68%, #fffaf2 100%);
    }

    .block-container {
        max-width: 1480px;
        padding-top: 1.25rem;
        padding-bottom: 4rem;
    }

    header[data-testid="stHeader"] {
        height: 0;
        min-height: 0;
        background: transparent;
        pointer-events: none;
    }

    div[data-testid="stToolbar"] {
        display: none;
        pointer-events: none;
    }

    .rp-topbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 18px;
        padding: 14px 18px;
        margin: 0 0 18px;
        border: 1px solid var(--rp-line);
        border-radius: 22px;
        background: rgba(255, 255, 255, 0.72);
        box-shadow: var(--rp-shadow-soft);
        backdrop-filter: blur(20px);
    }

    .rp-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 240px;
    }

    .rp-brand-mark {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 42px;
        height: 42px;
        border-radius: 13px;
        color: #ffffff;
        font-weight: 820;
        letter-spacing: 0;
        background: linear-gradient(135deg, #246bfe, #00a7b5 56%, #1b8f68);
        box-shadow: 0 12px 28px rgba(36, 107, 254, 0.22);
    }

    .rp-brand-title {
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 0;
        line-height: 1.1;
    }

    .rp-brand-subtitle,
    .rp-topbar-meta,
    .rp-eyebrow,
    .rp-muted {
        color: var(--rp-muted);
    }

    .rp-brand-subtitle {
        font-size: 12px;
        margin-top: 4px;
    }

    .rp-topbar-meta {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        justify-content: flex-end;
        font-size: 13px;
    }

    .rp-pill,
    .rp-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        border: 1px solid var(--rp-line);
        background: rgba(255, 255, 255, 0.72);
        color: #364052;
        font-size: 12px;
        font-weight: 650;
        line-height: 1;
        white-space: nowrap;
    }

    .rp-pill {
        padding: 8px 11px;
    }

    .rp-chip {
        padding: 7px 10px;
    }

    .rp-chip-blue {
        color: #154fc7;
        border-color: rgba(36, 107, 254, 0.24);
        background: rgba(36, 107, 254, 0.08);
    }

    .rp-chip-green {
        color: #0d7554;
        border-color: rgba(27, 143, 104, 0.24);
        background: rgba(27, 143, 104, 0.08);
    }

    .rp-chip-amber {
        color: #8a5b07;
        border-color: rgba(180, 123, 18, 0.28);
        background: rgba(180, 123, 18, 0.09);
    }

    .rp-hero {
        position: relative;
        overflow: hidden;
        border-radius: 28px;
        border: 1px solid rgba(106, 124, 152, 0.18);
        background:
            linear-gradient(120deg, rgba(255,255,255,0.96) 0%, rgba(247,251,255,0.9) 48%, rgba(239,249,245,0.92) 100%);
        box-shadow: var(--rp-shadow);
        padding: 34px;
        min-height: 326px;
    }

    .rp-hero::after {
        content: "";
        position: absolute;
        inset: auto -90px -120px 45%;
        height: 260px;
        background:
            linear-gradient(135deg, rgba(36,107,254,0.08), rgba(0,167,181,0.12), rgba(27,143,104,0.10));
        transform: rotate(-6deg);
        border-radius: 48px;
    }

    .rp-hero-grid {
        position: relative;
        z-index: 1;
        display: grid;
        grid-template-columns: minmax(0, 1.18fr) minmax(320px, 0.82fr);
        gap: 30px;
        align-items: center;
    }

    .rp-eyebrow {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 18px;
        font-size: 13px;
        font-weight: 700;
    }

    .rp-hero h1 {
        margin: 0;
        max-width: 850px;
        font-size: clamp(40px, 5vw, 66px);
        line-height: 1.02;
        letter-spacing: 0;
        color: #121926;
    }

    .rp-hero-lead {
        max-width: 790px;
        margin: 20px 0 0;
        color: #536174;
        font-size: 17px;
        line-height: 1.82;
    }

    .rp-search-shell {
        margin-top: 26px;
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 10px;
        max-width: 820px;
        padding: 8px;
        border: 1px solid rgba(36, 107, 254, 0.15);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.78);
        box-shadow: 0 18px 38px rgba(36, 107, 254, 0.10);
    }

    .rp-search-text {
        padding: 12px 14px;
        color: #2f3b4f;
        font-weight: 650;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .rp-search-action {
        padding: 12px 15px;
        border-radius: 13px;
        color: #ffffff;
        font-size: 13px;
        font-weight: 760;
        background: linear-gradient(135deg, #246bfe, #00a7b5);
        white-space: nowrap;
    }

    .rp-intel-panel {
        border: 1px solid rgba(107, 123, 148, 0.18);
        border-radius: 24px;
        background: rgba(255, 255, 255, 0.76);
        box-shadow: var(--rp-shadow-soft);
        backdrop-filter: blur(20px);
        padding: 18px;
    }

    .rp-intel-header {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: flex-start;
        margin-bottom: 14px;
    }

    .rp-intel-title {
        font-size: 16px;
        font-weight: 800;
    }

    .rp-intel-row {
        display: grid;
        grid-template-columns: 70px minmax(0, 1fr);
        gap: 12px;
        align-items: start;
        padding: 13px 0;
        border-top: 1px solid rgba(107, 123, 148, 0.14);
    }

    .rp-intel-row strong {
        display: block;
        margin-bottom: 4px;
        color: #202b3d;
    }

    .rp-intel-row span {
        color: #667386;
        font-size: 13px;
        line-height: 1.55;
    }

    .rp-section-head {
        margin: 28px 0 12px;
    }

    .rp-section-head h2 {
        margin: 0;
        font-size: 25px;
        letter-spacing: 0;
    }

    .rp-section-head p {
        margin: 8px 0 0;
        color: var(--rp-muted);
        line-height: 1.65;
    }

    .rp-metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin: 18px 0 8px;
    }

    .rp-metric-card,
    .rp-feature-card,
    .rp-data-card {
        border: 1px solid var(--rp-line);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.76);
        box-shadow: var(--rp-shadow-soft);
        backdrop-filter: blur(18px);
    }

    .rp-metric-card {
        padding: 18px;
    }

    .rp-metric-label {
        color: var(--rp-muted);
        font-size: 13px;
        font-weight: 650;
    }

    .rp-metric-value {
        margin-top: 8px;
        font-size: 30px;
        font-weight: 840;
        letter-spacing: 0;
        color: #142033;
    }

    .rp-metric-note {
        margin-top: 8px;
        color: #7a8596;
        font-size: 12px;
    }

    .rp-feature-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 16px;
    }

    .rp-feature-card {
        min-height: 174px;
        padding: 18px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .rp-feature-kicker {
        color: #246bfe;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
    }

    .rp-feature-card h3 {
        margin: 9px 0 8px;
        font-size: 20px;
        letter-spacing: 0;
    }

    .rp-feature-card p {
        margin: 0;
        color: #5c687a;
        line-height: 1.62;
    }

    .rp-feature-foot {
        margin-top: 16px;
        color: #3a4658;
        font-size: 13px;
        font-weight: 700;
    }

    .rp-data-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
    }

    .rp-data-card {
        padding: 14px;
    }

    .rp-data-card strong {
        display: block;
        margin-bottom: 8px;
    }

    .rp-data-card code {
        white-space: normal;
        word-break: break-word;
        color: #4d5b6f;
        background: rgba(233, 239, 247, 0.72);
        border-radius: 8px;
        padding: 2px 5px;
    }

    .rp-flow-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin: 14px 0 20px;
    }

    .rp-flow-step {
        position: relative;
        min-height: 92px;
        padding: 15px 16px;
        border: 1px solid rgba(107, 123, 148, 0.16);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.72);
        box-shadow: 0 12px 30px rgba(37, 48, 68, 0.07);
        backdrop-filter: blur(18px);
    }

    .rp-flow-step::before {
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        border-radius: 18px 0 0 18px;
        background: linear-gradient(180deg, #246bfe, #00a7b5, #1b8f68);
    }

    .rp-flow-index {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        margin-bottom: 8px;
        border-radius: 999px;
        color: #154fc7;
        background: rgba(36, 107, 254, 0.10);
        font-size: 12px;
        font-weight: 820;
    }

    .rp-flow-title {
        margin-bottom: 5px;
        font-size: 15px;
        font-weight: 820;
        color: #172033;
    }

    .rp-flow-copy {
        color: #607086;
        font-size: 13px;
        line-height: 1.58;
    }

    .rp-command-panel {
        margin: 8px 0 18px;
        padding: 1px;
        border-radius: 20px;
        background: linear-gradient(135deg, rgba(36, 107, 254, 0.22), rgba(0, 167, 181, 0.14), rgba(27, 143, 104, 0.18));
    }

    .rp-command-inner {
        border-radius: 19px;
        padding: 16px 18px;
        background: rgba(255, 255, 255, 0.86);
        box-shadow: var(--rp-shadow-soft);
    }

    .rp-command-title {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 8px;
    }

    .rp-command-title strong {
        font-size: 16px;
        color: #172033;
    }

    .rp-command-inner p {
        margin: 0;
        color: #607086;
        line-height: 1.62;
    }

    .rp-inline-stats {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin: 10px 0 18px;
    }

    .rp-inline-stat {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        min-height: 34px;
        padding: 8px 11px;
        border: 1px solid rgba(107, 123, 148, 0.16);
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.74);
        box-shadow: 0 8px 18px rgba(37, 48, 68, 0.05);
        color: #405066;
        font-size: 12px;
        font-weight: 700;
    }

    .rp-inline-stat b {
        color: #142033;
        font-size: 13px;
    }

    .rp-watch-card {
        min-height: 330px;
        padding: 18px;
        border: 1px solid rgba(107, 123, 148, 0.18);
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.76);
        box-shadow: var(--rp-shadow-soft);
        backdrop-filter: blur(18px);
    }

    .rp-watch-card-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(107, 123, 148, 0.14);
        margin-bottom: 13px;
    }

    .rp-watch-name {
        margin: 6px 0 0;
        color: #172033;
        font-size: 20px;
        font-weight: 840;
        line-height: 1.22;
        letter-spacing: 0;
    }

    .rp-kv-grid {
        display: grid;
        grid-template-columns: 1fr;
        gap: 9px;
    }

    .rp-kv-row {
        padding: 10px 11px;
        border: 1px solid rgba(107, 123, 148, 0.13);
        border-radius: 14px;
        background: rgba(248, 251, 255, 0.72);
    }

    .rp-kv-key {
        color: #6b7788;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: uppercase;
        margin-bottom: 7px;
    }

    .rp-kv-value {
        color: #273348;
        font-size: 13px;
        line-height: 1.55;
        word-break: break-word;
    }

    .rp-label-row {
        display: flex;
        align-items: center;
        gap: 7px;
        flex-wrap: wrap;
    }

    .rp-label-chip {
        display: inline-flex;
        align-items: center;
        min-height: 28px;
        padding: 6px 9px;
        border-radius: 999px;
        border: 1px solid rgba(36, 107, 254, 0.20);
        background: rgba(36, 107, 254, 0.08);
        color: #154fc7;
        font-size: 12px;
        font-weight: 760;
        line-height: 1;
    }

    .rp-paper-select-card {
        margin: 12px 0 16px;
        padding: 16px;
        border: 1px solid rgba(107, 123, 148, 0.16);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.76);
        box-shadow: var(--rp-shadow-soft);
        backdrop-filter: blur(16px);
    }

    .rp-window-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 2px 0 10px;
        border-bottom: 1px solid rgba(107, 123, 148, 0.14);
        margin-bottom: 14px;
    }

    .rp-window-dots {
        display: flex;
        gap: 7px;
    }

    .rp-dot {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        display: inline-flex;
    }

    .rp-dot-red { background: #ff6b6b; }
    .rp-dot-amber { background: #f6c253; }
    .rp-dot-green { background: #49c382; }

    .rp-field-label {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        margin: 10px 0 6px;
        font-weight: 820;
        color: #1d2838;
    }

    .rp-field-code {
        padding: 2px 7px;
        border-radius: 999px;
        background: rgba(36, 107, 254, 0.08);
        color: #246bfe;
        font-size: 12px;
        font-weight: 740;
    }

    .rp-card-preview-zh {
        color: #536174;
        line-height: 1.55;
        margin-bottom: 6px;
    }

    .rp-card-preview-en {
        color: #2f3b4f;
        line-height: 1.58;
    }

    div[data-testid="stTabs"] div[data-baseweb="tab-list"] {
        position: sticky;
        top: 10px;
        z-index: 20;
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        padding: 10px 10px 8px;
        margin-bottom: 18px;
        border: 1px solid rgba(107, 123, 148, 0.14);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.82);
        box-shadow: var(--rp-shadow-soft);
        backdrop-filter: blur(18px);
        overflow: visible;
        height: auto;
    }

    div[data-testid="stTabs"] button[role="tab"] {
        flex: 0 1 auto;
        min-height: 42px;
        border-radius: 13px;
        padding: 8px 12px;
        color: #465366;
        font-weight: 720;
    }

    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
        color: #12305f;
        background: rgba(36, 107, 254, 0.10);
    }

    div[data-testid="stTabs"] div[data-baseweb="tab-highlight"] {
        display: none;
    }

    div[data-testid="stTabs"] button[aria-label="Scroll tabs left"],
    div[data-testid="stTabs"] button[aria-label="Scroll tabs right"] {
        display: none;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 18px;
        border-color: rgba(107, 123, 148, 0.20);
        background: rgba(255, 255, 255, 0.78);
        box-shadow: var(--rp-shadow-soft);
        backdrop-filter: blur(18px);
    }

    div[data-testid="stPopover"] button,
    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button,
    div[data-testid="stFormSubmitButton"] button {
        border-radius: 13px;
        font-weight: 760;
        border-color: rgba(107, 123, 148, 0.18);
        box-shadow: 0 8px 20px rgba(37, 48, 68, 0.06);
    }

    div[data-testid="stMetric"] {
        border: 1px solid rgba(107, 123, 148, 0.16);
        border-radius: 16px;
        padding: 12px 14px;
        background: rgba(255, 255, 255, 0.68);
    }

    div[data-testid="stDataFrame"] {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid rgba(107, 123, 148, 0.14);
        box-shadow: var(--rp-shadow-soft);
    }

    textarea,
    input,
    div[data-baseweb="select"] > div {
        border-radius: 13px !important;
    }

    div[data-testid="stTextInput"] label,
    div[data-testid="stTextArea"] label,
    div[data-testid="stSelectbox"] label,
    div[data-testid="stSlider"] label,
    div[data-testid="stCheckbox"] label,
    div[data-testid="stFileUploader"] label,
    div[data-testid="stMultiSelect"] label {
        color: #2f3b4f;
        font-weight: 720;
    }

    div[data-testid="stForm"] {
        padding: 18px;
        border: 1px solid rgba(107, 123, 148, 0.18);
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.70);
        box-shadow: var(--rp-shadow-soft);
        backdrop-filter: blur(16px);
    }

    div[data-testid="stExpander"] {
        border: 1px solid rgba(107, 123, 148, 0.16);
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.68);
        box-shadow: 0 10px 24px rgba(37, 48, 68, 0.05);
        overflow: hidden;
    }

    div[data-testid="stAlert"] {
        border-radius: 16px;
        border-color: rgba(107, 123, 148, 0.16);
        box-shadow: 0 8px 18px rgba(37, 48, 68, 0.04);
    }

    div[data-testid="stFileUploader"] section {
        border-radius: 18px;
        border-color: rgba(36, 107, 254, 0.20);
        background: rgba(255, 255, 255, 0.72);
    }

    div[data-testid="stChatInput"] {
        border-radius: 18px;
        box-shadow: var(--rp-shadow-soft);
    }

    hr {
        margin: 1.4rem 0;
        border-color: rgba(107, 123, 148, 0.14);
    }

    h3 {
        letter-spacing: 0;
    }

    .stChatMessage {
        border-radius: 18px;
        border: 1px solid rgba(107, 123, 148, 0.14);
        background: rgba(255, 255, 255, 0.72);
        box-shadow: var(--rp-shadow-soft);
    }

    @media (max-width: 1100px) {
        .rp-hero-grid,
        .rp-feature-grid,
        .rp-flow-grid,
        .rp-metric-grid,
        .rp-data-grid {
            grid-template-columns: 1fr 1fr;
        }
    }

    @media (max-width: 760px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        .rp-topbar,
        .rp-topbar-meta {
            align-items: flex-start;
            justify-content: flex-start;
        }
        .rp-topbar,
        .rp-hero-grid,
        .rp-feature-grid,
        .rp-flow-grid,
        .rp-metric-grid,
        .rp-data-grid,
        .rp-search-shell {
            grid-template-columns: 1fr;
            flex-direction: column;
        }
        .rp-hero {
            padding: 24px;
            border-radius: 22px;
        }
        .rp-search-action {
            text-align: center;
        }
    }
    </style>
    """
)


def _render_app_shell() -> None:
    status = agent_bridge_status()
    codex_status = "Codex 可用" if status["codex_available"] else "Codex 未连接"
    opencode_status = "OpenCode 可用" if status["opencode_available"] else "OpenCode 未连接"
    st.html(
        f"""
        <div class="rp-topbar">
            <div class="rp-brand">
                <div class="rp-brand-mark">RP</div>
                <div>
                    <div class="rp-brand-title">ResearchPilot</div>
                    <div class="rp-brand-subtitle">面向科研方向发现、论文卡片与本地 agent 协作的工作台</div>
                </div>
            </div>
            <div class="rp-topbar-meta">
                <span class="rp-pill">中文首页</span>
                <span class="rp-pill">CCF Venue Discovery</span>
                <span class="rp-pill">{_escape_html(codex_status)}</span>
                <span class="rp-pill">{_escape_html(opencode_status)}</span>
            </div>
        </div>
        """
    )


def _render_section_header(title: str, subtitle: str = "", kicker: str = "") -> None:
    kicker_html = f'<div class="rp-eyebrow">{_escape_html(kicker)}</div>' if kicker else ""
    subtitle_html = f"<p>{_escape_html(subtitle)}</p>" if subtitle else ""
    st.html(
        f"""
        <div class="rp-section-head">
            {kicker_html}
            <h2>{_escape_html(title)}</h2>
            {subtitle_html}
        </div>
        """
    )


_render_app_shell()

if "pipeline" not in st.session_state:
    st.session_state["pipeline"] = ResearchPilotPipeline()
if "paper_cards" not in st.session_state:
    st.session_state["paper_cards"] = load_paper_cards_cache()
if "paper_labels" not in st.session_state:
    st.session_state["paper_labels"] = load_paper_labels()
if "literature_review" not in st.session_state:
    st.session_state["literature_review"] = ""
if "claim_verification" not in st.session_state:
    st.session_state["claim_verification"] = []
if "revised_literature_review" not in st.session_state:
    st.session_state["revised_literature_review"] = ""
if "review_versions" not in st.session_state:
    st.session_state["review_versions"] = []
if "active_review_version" not in st.session_state:
    st.session_state["active_review_version"] = 0
if "pending_active_review_version" not in st.session_state:
    st.session_state["pending_active_review_version"] = None
if "arxiv_results" not in st.session_state:
    st.session_state["arxiv_results"] = []
if "arxiv_topic" not in st.session_state:
    st.session_state["arxiv_topic"] = ""
if "review_topic" not in st.session_state:
    st.session_state["review_topic"] = ""
if "research_ideas" not in st.session_state:
    st.session_state["research_ideas"] = ""
if "watchlist" not in st.session_state:
    try:
        st.session_state["watchlist"] = load_watchlist()
    except Exception:
        st.session_state["watchlist"] = []
if "watchlist_trend_summary" not in st.session_state:
    st.session_state["watchlist_trend_summary"] = ""
if "watchlist_tracking" not in st.session_state:
    try:
        st.session_state["watchlist_tracking"] = load_watchlist_tracking()
    except Exception:
        st.session_state["watchlist_tracking"] = {}
if "venue_plan" not in st.session_state:
    st.session_state["venue_plan"] = None
if "venue_collection" not in st.session_state:
    st.session_state["venue_collection"] = None
if "venue_report_draft" not in st.session_state:
    st.session_state["venue_report_draft"] = ""
if "workspace_chat_messages" not in st.session_state:
    st.session_state["workspace_chat_messages"] = []
if "workspace_chat_draft" not in st.session_state:
    st.session_state["workspace_chat_draft"] = ""

pipeline: ResearchPilotPipeline = st.session_state["pipeline"]
paper_cards: dict[str, dict] = st.session_state["paper_cards"]
paper_labels: dict[str, list[str]] = st.session_state["paper_labels"]
literature_review: str = st.session_state["literature_review"]
claim_verification: list[dict] = st.session_state["claim_verification"]
revised_literature_review: str = st.session_state["revised_literature_review"]
review_versions: list[dict] = st.session_state["review_versions"]
active_review_version: int = st.session_state["active_review_version"]
arxiv_results: list[dict] = st.session_state["arxiv_results"]
arxiv_topic: str = st.session_state["arxiv_topic"]
research_ideas: str = st.session_state["research_ideas"]
watchlist: list[dict] = st.session_state["watchlist"]
watchlist_trend_summary: str = st.session_state["watchlist_trend_summary"]
watchlist_tracking: dict[str, dict] = st.session_state["watchlist_tracking"]
venue_plan: dict | None = st.session_state["venue_plan"]
venue_collection: dict | None = st.session_state["venue_collection"]

def _arxiv_selection_key(paper: dict, rank: int) -> str:
    base_id = str(paper.get("arxiv_id") or paper.get("entry_id") or f"rank_{rank}")
    normalized = "".join(ch if ch.isalnum() else "_" for ch in base_id)
    normalized = normalized.strip("_") or f"rank_{rank}"
    return f"arxiv_select_{normalized[:100]}_{rank}"


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def _current_topic_hint() -> str:
    collection = st.session_state.get("venue_collection")
    if isinstance(collection, dict) and str(collection.get("topic", "")).strip():
        return str(collection.get("topic", "")).strip()
    for key in ["review_topic", "arxiv_topic", "research_ideas_topic"]:
        value = str(st.session_state.get(key, "") or "").strip()
        if value:
            return value
    return "形式化验证与大模型结合"


def _render_metric_grid(metrics: list[tuple[str, object, str]]) -> None:
    cards = []
    for label, value, note in metrics:
        cards.append(
            f"""
            <div class="rp-metric-card">
                <div class="rp-metric-label">{_escape_html(label)}</div>
                <div class="rp-metric-value">{_escape_html(value)}</div>
                <div class="rp-metric-note">{_escape_html(note)}</div>
            </div>
            """
        )
    st.html(f'<div class="rp-metric-grid">{"".join(cards)}</div>')


def _render_feature_grid(features: list[dict[str, str]]) -> None:
    cards = []
    for item in features:
        chips = "".join(
            f'<span class="rp-chip {chip.get("class", "")}">{_escape_html(chip.get("label", ""))}</span>'
            for chip in item.get("chips", [])
        )
        cards.append(
            f"""
            <div class="rp-feature-card">
                <div>
                    <div class="rp-feature-kicker">{_escape_html(item.get("kicker", ""))}</div>
                    <h3>{_escape_html(item.get("title", ""))}</h3>
                    <p>{_escape_html(item.get("text", ""))}</p>
                </div>
                <div>
                    <div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:16px;">{chips}</div>
                    <div class="rp-feature-foot">{_escape_html(item.get("foot", ""))}</div>
                </div>
            </div>
            """
        )
    st.html(f'<div class="rp-feature-grid">{"".join(cards)}</div>')


def _render_data_grid(items: list[tuple[str, str, str]]) -> None:
    cards = []
    for title, path, note in items:
        cards.append(
            f"""
            <div class="rp-data-card">
                <strong>{_escape_html(title)}</strong>
                <code>{_escape_html(path)}</code>
                <div class="rp-muted" style="margin-top:10px;font-size:12px;line-height:1.55;">{_escape_html(note)}</div>
            </div>
            """
        )
    st.html(f'<div class="rp-data-grid">{"".join(cards)}</div>')


def _render_workflow_strip(steps: list[tuple[str, str]]) -> None:
    cards = []
    for idx, (title, copy) in enumerate(steps, start=1):
        cards.append(
            f"""
            <div class="rp-flow-step">
                <div class="rp-flow-index">{idx:02d}</div>
                <div class="rp-flow-title">{_escape_html(title)}</div>
                <div class="rp-flow-copy">{_escape_html(copy)}</div>
            </div>
            """
        )
    st.html(f'<div class="rp-flow-grid">{"".join(cards)}</div>')


def _render_command_panel(
    title: str,
    body: str,
    chips: list[str] | None = None,
) -> None:
    chips = chips or []
    chip_html = "".join(
        f'<span class="rp-chip rp-chip-blue">{_escape_html(chip)}</span>'
        for chip in chips
    )
    st.html(
        f"""
        <div class="rp-command-panel">
            <div class="rp-command-inner">
                <div class="rp-command-title">
                    <strong>{_escape_html(title)}</strong>
                    <div style="display:flex;gap:7px;flex-wrap:wrap;justify-content:flex-end;">{chip_html}</div>
                </div>
                <p>{_escape_html(body)}</p>
            </div>
        </div>
        """
    )


def _render_inline_stats(items: list[tuple[str, object]]) -> None:
    stats = []
    for label, value in items:
        stats.append(
            f"""
            <span class="rp-inline-stat">
                <span>{_escape_html(label)}</span>
                <b>{_escape_html(value)}</b>
            </span>
            """
        )
    st.html(f'<div class="rp-inline-stats">{"".join(stats)}</div>')


def _render_home() -> None:
    cards_count = len(paper_cards)
    ingested_count = len(pipeline.list_papers())
    reports_count = len(list_workspace_reports(limit=50))
    watch_count = len(st.session_state.get("watchlist", []))
    status = agent_bridge_status()
    task_count = len(list_agent_tasks(limit=20))
    topic_hint = _current_topic_hint()
    codex_badge = "Codex 可直接委托" if status["codex_available"] else "Codex CLI 未发现"
    opencode_badge = "OpenCode 可直接委托" if status["opencode_available"] else "OpenCode CLI 未发现"

    st.html(
        f"""
        <section class="rp-hero">
            <div class="rp-hero-grid">
                <div>
                    <div class="rp-eyebrow">
                        <span class="rp-chip rp-chip-blue">ResearchPilot · 本地科研工作台</span>
                        <span class="rp-chip rp-chip-green">Agent-native generation</span>
                        <span class="rp-chip rp-chip-amber">CCF / OpenReview / Scholar APIs</span>
                    </div>
                    <h1>从方向发现到可验证综述的科研情报工作台</h1>
                    <p class="rp-hero-lead">
                        以 topic 为入口规划 CCF 会议/期刊，聚合 arXiv、OpenReview、OpenAlex、Semantic Scholar 与本地文献，
                        生成双语 paper cards、comparison table、调研报告，并把 Codex/OpenCode 接入网页端任务流。
                    </p>
                    <div class="rp-search-shell">
                        <div class="rp-search-text">当前建议检索方向：{_escape_html(topic_hint)}</div>
                        <div class="rp-search-action">前往 Research Discovery</div>
                    </div>
                </div>
                <aside class="rp-intel-panel">
                    <div class="rp-intel-header">
                        <div>
                            <div class="rp-intel-title">科研情报流</div>
                            <div class="rp-muted" style="font-size:12px;margin-top:4px;">参考 AMiner 的报告、学者图谱与订阅式发现体验</div>
                        </div>
                        <span class="rp-chip rp-chip-blue">Live Workspace</span>
                    </div>
                    <div class="rp-intel-row">
                        <span class="rp-chip">01</span>
                        <div><strong>Topic → Venue Plan</strong><span>根据研究方向选择 AI、PL、FM、SE 等交叉 venue，并保留 Google Scholar 补查入口。</span></div>
                    </div>
                    <div class="rp-intel-row">
                        <span class="rp-chip">02</span>
                        <div><strong>Paper Cards → Report</strong><span>将论文元数据和本地 PDF 统一成可编辑卡片，再汇总成报告草稿。</span></div>
                    </div>
                    <div class="rp-intel-row">
                        <span class="rp-chip">03</span>
                        <div><strong>Watchlist → Scholar Graph</strong><span>把学者、课题组和机构加入关注流，形成后续推荐和追踪依据。</span></div>
                    </div>
                </aside>
            </div>
        </section>
        """
    )

    _render_metric_grid(
        [
            ("Paper Cards", cards_count, "已缓存、可双语编辑"),
            ("已入库论文", ingested_count, "可用于 RAG 和引用验证"),
            ("Workspace 报告", reports_count, "已批准保存的调研资产"),
            ("Bridge Tasks", task_count, "Codex / OpenCode 委托任务"),
        ]
    )

    _render_section_header(
        "功能导航",
        "入口仍然使用顶部标签页；首页承担方向选择、能力导览和数据资产索引。",
        "Application map",
    )
    _render_feature_grid(
        [
            {
                "kicker": "Discovery",
                "title": "Research Discovery",
                "text": "按 topic 推断 CCF 会议/期刊，采集近期论文，生成调研报告与 metadata paper cards。",
                "foot": "顶部标签：Research Discovery",
                "chips": [{"label": "CCF"}, {"label": "OpenReview"}, {"label": "Semantic Scholar"}],
            },
            {
                "kicker": "Cards",
                "title": "Paper Cards",
                "text": "查看、编辑和双语化论文卡片，字段逐项保存，适合后续 comparison table 和报告生成。",
                "foot": "顶部标签：Paper Cards",
                "chips": [{"label": "双语", "class": "rp-chip-green"}, {"label": "可编辑"}],
            },
            {
                "kicker": "Workspace",
                "title": "Workspace Chat",
                "text": "读取 paper cards、入库论文、watchlist 和报告，支持比较、问答、报告预览与批准保存。",
                "foot": "顶部标签：Workspace Chat",
                "chips": [{"label": "Codex", "class": "rp-chip-blue"}, {"label": "OpenCode"}],
            },
            {
                "kicker": "Review",
                "title": "Literature Review",
                "text": "基于 paper cards 生成综述，并做 claim-level citation verification 与保守改写。",
                "foot": "顶部标签：Literature Review",
                "chips": [{"label": "Citation check", "class": "rp-chip-amber"}],
            },
            {
                "kicker": "People",
                "title": "Watchlist",
                "text": "管理学者、课题组、机构和关键词；推荐卡片可一键加入关注流。",
                "foot": "顶部标签：Watchlist",
                "chips": [{"label": "学者"}, {"label": "课题组"}, {"label": "机构"}],
            },
            {
                "kicker": "Library",
                "title": "Current Library",
                "text": "快速核对已入库论文、缓存 paper cards、workspace 报告和当前数据状态。",
                "foot": "顶部标签：Current Library",
                "chips": [{"label": "Local-first", "class": "rp-chip-green"}],
            },
        ]
    )

    _render_section_header(
        "数据模块",
        "这些文件和目录是网页端与本地 agent 端对齐的共享状态。",
        "Workspace assets",
    )
    _render_data_grid(
        [
            ("Paper cards", "data/outputs/paper_cards_cache.json", "双语卡片、字段编辑和 comparison table 的主缓存。"),
            ("Venue collection", "data/agent_state/last_venue_collection.json", "最近一次跨 venue / 学术搜索采集结果。"),
            ("Watchlist tracking", "data/outputs/watchlist_tracking.json", "学者/课题组/机构主页索引、近期论文和已忽略推荐。"),
            ("Workspace reports", "data/outputs/workspace/", "用户批准保存后的报告和对话产物。"),
            ("Agent bridge tasks", "data/outputs/agent_bridge/tasks/", "网页端委托 Codex/OpenCode 的任务队列。"),
        ]
    )

    _render_section_header(
        "本地 Agent 生成通道",
        f"{codex_badge} · {opencode_badge} · 任务队列：{status['tasks_dir']}",
        "Agent bridge",
    )


def _split_csv_or_lines(text: str) -> list[str]:
    parts = re.split(r"[\n,]+", str(text or ""))
    return [part.strip() for part in parts if part.strip()]


def _parse_years(text: str) -> list[int]:
    years: list[int] = []
    for item in _split_csv_or_lines(text):
        try:
            year = int(item)
        except Exception:
            continue
        if 1900 <= year <= 2100 and year not in years:
            years.append(year)
    return sorted(years, reverse=True)


def _backend_llm_configured() -> bool:
    return bool((get_config().openai_api_key or "").strip())


def _compact_json(payload: object, limit: int = 28000) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if len(text) <= limit:
        return text
    return text[: limit - 200] + "\n... [truncated]\n"


def _extract_json_object(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start : end + 1])
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
    return {}


def _safe_widget_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "item"))[:120]


def _join_display(values: object, empty: str = "未记录") -> str:
    items = [str(item).strip() for item in (values or []) if str(item).strip()] if isinstance(values, list) else []
    if not items:
        return empty
    return " / ".join(items)


def _render_chips(values: object, class_name: str = "rp-label-chip", empty: str = "未标记") -> str:
    items = normalize_labels(values)
    if not items:
        return f'<span class="{class_name}">{_escape_html(empty)}</span>'
    return "".join(f'<span class="{class_name}">{_escape_html(item)}</span>' for item in items)


def _paper_title_for_select(paper_id: str) -> str:
    card = paper_cards.get(paper_id)
    if isinstance(card, dict):
        title = str(card.get("title", "") or "").strip()
        if title:
            return title
        source_meta = card.get("source_metadata", {})
        if isinstance(source_meta, dict) and source_meta.get("title"):
            return str(source_meta.get("title", "")).strip()
    return str(paper_id)


def _paper_option_label(paper_id: str) -> str:
    title = _paper_title_for_select(paper_id)
    labels = labels_for_paper(paper_id, paper_labels)
    suffix = f" [{', '.join(labels)}]" if labels else " [未标记]"
    return f"{title}{suffix}"


def _paper_payload_for_labeling(paper_id: str) -> dict:
    card = paper_cards.get(paper_id)
    if not isinstance(card, dict):
        return {
            "paper_id": paper_id,
            "title": _paper_title_for_select(paper_id),
            "labels": labels_for_paper(paper_id, paper_labels),
        }
    return {
        "paper_id": paper_id,
        "title": _paper_title_for_select(paper_id),
        "problem": card.get("problem", ""),
        "method": card.get("method", ""),
        "contribution": card.get("contribution", ""),
        "relevance": card.get("relevance", ""),
        "source_metadata": card.get("source_metadata", {}),
        "labels": labels_for_paper(paper_id, paper_labels),
    }


def _agent_label_prompt(target_paper_ids: list[str], existing_labels: list[str]) -> str:
    papers = [
        _paper_payload_for_labeling(paper_id)
        for paper_id in target_paper_ids
        if not labels_for_paper(paper_id, paper_labels)
    ]
    schema = {
        "assignments": [
            {
                "paper_id": "string",
                "labels": ["existing or new label"],
                "reason": "brief Chinese reason",
                "is_new_label": False,
            }
        ]
    }
    return (
        "你是 ResearchPilot 的本地科研分类 agent。请只给尚未分配 label 的论文分配类别。"
        "如果现有类别足够贴切，优先使用现有类别；如果没有合适类别，可以创建新的简短中文或英文类别。"
        "每篇论文最多给 1-2 个 label。不要修改已有 label 的论文。只返回严格 JSON 对象，不要 Markdown。\n\n"
        f"目标 JSON schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"现有类别:\n{json.dumps(existing_labels, ensure_ascii=False, indent=2)}\n\n"
        f"待分类论文:\n{_compact_json(papers, limit=52000)}"
    )


def _apply_agent_label_assignments(response_text: str) -> tuple[int, list[str]]:
    parsed = _extract_json_object(response_text)
    assignments = parsed.get("assignments", []) if isinstance(parsed, dict) else []
    if not isinstance(assignments, list):
        return 0, ["Agent response did not contain an assignments list."]

    labels = load_paper_labels()
    applied = 0
    skipped: list[str] = []
    for item in assignments:
        if not isinstance(item, dict):
            continue
        paper_id = str(item.get("paper_id", "")).strip()
        if not paper_id:
            continue
        if labels_for_paper(paper_id, labels):
            skipped.append(f"{paper_id}: already labeled")
            continue
        label_values = normalize_labels(item.get("labels", []))
        if not label_values:
            skipped.append(f"{paper_id}: no labels returned")
            continue
        labels[paper_id] = label_values[:2]
        applied += 1
    if applied:
        save_paper_labels(labels)
        st.session_state["paper_labels"] = labels
    return applied, skipped


def _render_watch_card(item: dict, idx: int) -> None:
    item_name = str(item.get("name", ""))
    item_type = str(item.get("type", "custom") or "custom")
    safe_name = _safe_widget_key(item_name)
    authors = item.get("authors", []) or []
    institutions = item.get("institutions", []) or []
    keywords = item.get("keywords", []) or []
    homepage_urls = item.get("homepage_urls", []) or []
    notes = str(item.get("notes", "") or "").strip()
    tracking = (
        st.session_state.get("watchlist_tracking", {}).get(watch_item_key(item))
        or get_watch_item_tracking(item)
    )
    tracked_count = int((tracking or {}).get("paper_count", 0) or 0)
    st.html(
        f"""
        <div class="rp-watch-card">
            <div class="rp-watch-card-head">
                <div>
                    <span class="rp-chip rp-chip-blue">{_escape_html(item_type)}</span>
                    <div class="rp-watch-name">{_escape_html(item_name)}</div>
                </div>
                <span class="rp-chip rp-chip-green">{tracked_count} papers</span>
            </div>
            <div class="rp-kv-grid">
                <div class="rp-kv-row">
                    <div class="rp-kv-key">authors</div>
                    <div class="rp-label-row">{_render_chips(authors, class_name="rp-chip", empty="未记录")}</div>
                </div>
                <div class="rp-kv-row">
                    <div class="rp-kv-key">institutions</div>
                    <div class="rp-kv-value">{_escape_html(_join_display(institutions))}</div>
                </div>
                <div class="rp-kv-row">
                    <div class="rp-kv-key">keywords</div>
                    <div class="rp-label-row">{_render_chips(keywords, class_name="rp-chip rp-chip-amber", empty="未记录")}</div>
                </div>
                <div class="rp-kv-row">
                    <div class="rp-kv-key">homepage / profiles</div>
                    <div class="rp-kv-value">{_escape_html(_join_display(homepage_urls))}</div>
                </div>
                <div class="rp-kv-row">
                    <div class="rp-kv-key">notes</div>
                    <div class="rp-kv-value">{_escape_html(notes or "未记录")}</div>
                </div>
            </div>
        </div>
        """
    )
    action_cols = st.columns([1, 1, 1])
    if _should_track_watch_item(item):
        if action_cols[0].button(
            "追踪论文",
            key=f"watchlist_track_card_{idx}_{safe_name}",
            width="stretch",
        ):
            try:
                with st.spinner("正在检索主页索引与近 6 个月论文..."):
                    tracking = _refresh_watch_item_tracking(item, months=6, max_results=25)
                st.success(f"追踪完成：发现 {tracking.get('paper_count', 0)} 篇候选论文。")
                st.rerun()
            except Exception as exc:
                st.error(f"追踪失败：{exc}")
    with action_cols[1].popover("详情", use_container_width=True):
        st.json(item)
        st.markdown("#### 主页 / 学术索引")
        _render_homepage_index(homepage_index_for_watch_item(item))
        if tracking:
            st.markdown("#### 主页索引与近 6 个月论文")
            _render_tracking_papers(item, tracking, idx)
    if action_cols[2].button(
        "Delete",
        key=f"watchlist_delete_card_{idx}_{safe_name}",
        width="stretch",
    ):
        try:
            updated_watchlist = delete_watch_item(idx)
            st.session_state["watchlist"] = updated_watchlist
            st.success(f"Deleted watch item: {item_name}")
            st.rerun()
        except Exception as exc:
            st.error(f"Failed to delete watch item: {exc}")


def _collection_rows(collection: dict | None) -> list[dict]:
    if not collection:
        return []
    papers = collection.get("papers", [])
    if not isinstance(papers, list):
        return []
    rows = []
    for idx, paper in enumerate(papers, start=1):
        if not isinstance(paper, dict):
            continue
        rows.append(
            {
                "rank": idx,
                "title": paper.get("title", ""),
                "year": paper.get("year", ""),
                "source": paper.get("source", ""),
                "venue": paper.get("venue", ""),
                "target_venue": paper.get("target_venue", ""),
                "scope": paper.get("collection_scope", ""),
                "score": paper.get("relevance_score", ""),
                "url": paper.get("source_url", ""),
            }
        )
    return rows


def _generate_backend_venue_report(collection: dict, focus: str) -> str:
    compact = {
        "topic": collection.get("topic", ""),
        "collected_at": collection.get("collected_at", ""),
        "years": collection.get("years", []),
        "plan": collection.get("plan", {}),
        "papers": collection.get("papers", [])[:35],
        "warnings": collection.get("warnings", []),
    }
    system_prompt = (
        "你是严谨的科研文献调研助手。只能基于用户提供的会议/期刊/学术搜索元数据和摘要写作。"
        "输出中文 Markdown，不要声称检索已穷尽；区分 target_venue 和 venue；"
        "broad_openalex / broad_semantic_scholar 只能作为相关命中。"
    )
    user_prompt = (
        f"调研重点：{focus or collection.get('topic', '')}\n\n"
        "请生成一份结构化调研报告，包含：检索范围与来源、CCF venue 覆盖、代表性论文、"
        "主题聚类、交叉方向观察、可能遗漏与 Google Scholar 补查链接、后续精读建议。\n\n"
        f"采集数据：\n{_compact_json(compact)}"
    )
    return chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )


def _agent_report_prompt(collection: dict, focus: str) -> str:
    compact = {
        "topic": collection.get("topic", ""),
        "collected_at": collection.get("collected_at", ""),
        "years": collection.get("years", []),
        "plan": collection.get("plan", {}),
        "papers": collection.get("papers", [])[:35],
        "warnings": collection.get("warnings", []),
    }
    return (
        "你是 ResearchPilot 的本地科研 agent。请只基于下面 collection 元数据和摘要写一份中文 Markdown 调研报告，"
        "不要修改任何文件，不要调用外部命令，不要声称检索已穷尽。\n\n"
        "要求结构：# 论文搜集报告；## 1. 检索范围与来源；## 2. CCF相关会议/期刊覆盖；"
        "## 3. 代表性论文；## 4. 主题聚类；## 5. 交叉方向观察；"
        "## 6. 可能遗漏与Google Scholar补查链接；## 7. 后续精读建议。\n\n"
        f"调研重点：{focus or collection.get('topic', '')}\n\n"
        "注意区分 target_venue 与 venue；broad_openalex / broad_semantic_scholar 只能作为相关命中。\n\n"
        f"Collection JSON:\n{_compact_json(compact, limit=52000)}"
    )


def _agent_bilingual_card_prompt(card: dict) -> str:
    schema = {
        "paper_id": "string",
        "title": "string",
        "problem": "English string",
        "method": "English string",
        "contribution": "English string",
        "dataset": "English string",
        "result": "English string",
        "limitation": "English string",
        "future_work": "English string",
        "relevance": "English string",
        "zh": {
            "title": "中文标题或原题名",
            "problem": "中文",
            "method": "中文",
            "contribution": "中文",
            "dataset": "中文",
            "result": "中文",
            "limitation": "中文",
            "future_work": "中文",
            "relevance": "中文",
        },
    }
    return (
        "你是 ResearchPilot 的本地科研 agent。请把下面 paper card 转成严格 JSON，保留事实不确定性，"
        "不要编造数据集、结果或方法。只返回 JSON 对象，不要 Markdown。\n\n"
        f"目标 schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"Source card:\n{_compact_json(card, limit=36000)}"
    )


def _run_or_queue_agent_generation(
    *,
    provider: str,
    task_type: str,
    prompt: str,
    model: str = "",
    timeout_seconds: int = 300,
    payload: dict | None = None,
) -> dict:
    normalized_provider = str(provider or "queue").lower()
    if normalized_provider == "queue":
        task = queue_agent_task(
            task_type=task_type,
            prompt=prompt,
            provider="codex",
            payload=payload,
        )
        return {
            "mode": "queued",
            "output": (
                f"已创建本地 agent task。\n\n"
                f"- prompt: `{task['prompt_path']}`\n"
                f"- result: `{task['result_path']}`\n\n"
                "你可以让 Codex/OpenCode 读取 prompt 文件完成任务，或切换 provider 为 codex/opencode 直接运行。"
            ),
            "task": task,
        }
    result = run_agent_task(
        task_type=task_type,
        prompt=prompt,
        provider=normalized_provider,
        model=model.strip() or None,
        timeout_seconds=timeout_seconds,
        payload=payload,
    )
    return {"mode": "executed", "output": result.get("output", ""), "task": result}


FIELD_LABELS_ZH = {
    "problem": "研究问题",
    "method": "方法",
    "contribution": "贡献",
    "dataset": "数据/基准",
    "result": "结果",
    "limitation": "局限",
    "future_work": "后续工作",
    "relevance": "相关性",
}


def _card_preview(text: str, limit: int = 260) -> str:
    normalized = str(text or "").replace("\n", " ").strip()
    if len(normalized) <= limit:
        return normalized or "Not specified."
    return normalized[: limit - 3].rstrip() + "..."


def _save_card_field(
    *,
    paper_id: str,
    card: dict,
    field: str,
    english_value: str,
    chinese_value: str,
) -> None:
    card[field] = english_value
    zh = card.get("zh")
    if not isinstance(zh, dict):
        zh = {}
    zh[field] = chinese_value
    card["zh"] = zh
    paper_cards[paper_id] = card
    save_paper_cards_cache(paper_cards)
    st.session_state["paper_cards"] = paper_cards


def _render_paper_card(card: dict, card_key: str) -> None:
    title = str(card.get("title", "") or card.get("paper_id", "Untitled"))
    paper_id = str(card.get("paper_id", ""))
    key_base = _safe_widget_key(card_key or paper_id or title)
    source_meta = card.get("source_metadata", {}) if isinstance(card.get("source_metadata"), dict) else {}
    chips: list[str] = []
    for label, value in [
        ("paper_id", paper_id),
        ("source", source_meta.get("source", "")),
        ("venue", source_meta.get("venue", "")),
        ("year", source_meta.get("year", "")),
        ("scope", source_meta.get("collection_scope", "")),
    ]:
        if value:
            chips.append(f"{label}: {value}")

    zh = card.get("zh", {}) if isinstance(card.get("zh"), dict) else {}
    with st.container(border=True):
        st.html(
            """
            <div class="rp-window-bar">
                <div class="rp-window-dots">
                    <span class="rp-dot rp-dot-red"></span>
                    <span class="rp-dot rp-dot-amber"></span>
                    <span class="rp-dot rp-dot-green"></span>
                </div>
                <span class="rp-chip rp-chip-blue">Paper Card</span>
            </div>
            """
        )
        title_col, action_col = st.columns([0.78, 0.22], vertical_alignment="top")
        with title_col:
            chip_html = "".join(
                f'<span class="rp-chip">{_escape_html(chip)}</span>' for chip in chips[:8]
            )
            st.html(
                f"""
                <div>
                    <h2 style="margin:0 0 10px;font-size:25px;line-height:1.25;letter-spacing:0;color:#141d2b;">
                        {_escape_html(title)}
                    </h2>
                    <div style="display:flex;gap:7px;flex-wrap:wrap;margin-bottom:6px;">{chip_html}</div>
                </div>
                """
            )
        with action_col:
            with st.popover("Edit Title", use_container_width=True):
                title_value = st.text_input(
                    "Title",
                    value=title,
                    key=f"card_{key_base}_title_value",
                )
                zh_title_value = st.text_input(
                    "中文标题",
                    value=str(zh.get("title", "") or title),
                    key=f"card_{key_base}_zh_title_value",
                )
                if st.button("Save Title", key=f"card_{key_base}_title_save", width="stretch"):
                    card["title"] = title_value
                    zh = card.get("zh") if isinstance(card.get("zh"), dict) else {}
                    zh["title"] = zh_title_value
                    card["zh"] = zh
                    paper_cards[card_key] = card
                    save_paper_cards_cache(paper_cards)
                    st.session_state["paper_cards"] = paper_cards
                    st.success("Title saved.")
                    st.rerun()

        field_columns = st.columns(2)
        visible_fields = [field for field in CARD_FIELDS if field not in {"paper_id", "title"}]
        for idx, field in enumerate(visible_fields):
            if field in {"paper_id", "title"}:
                continue
            en_text = str(card.get(field, "") or "").strip()
            zh_text = str(zh.get(field, "") or "").strip()
            if not en_text and not zh_text:
                continue

            with field_columns[idx % 2]:
                st.html(
                    f"""
                    <div class="rp-field-label">
                        <span>{_escape_html(FIELD_LABELS_ZH.get(field, field))}</span>
                        <span class="rp-field-code">/{_escape_html(field)}</span>
                    </div>
                    <div class="rp-card-preview-zh">{_escape_html(_card_preview(zh_text, 140))}</div>
                    <div class="rp-card-preview-en">{_escape_html(_card_preview(en_text, 240))}</div>
                    """
                )
                with st.popover(f"Edit {FIELD_LABELS_ZH.get(field, field)}", use_container_width=True):
                    zh_value = st.text_area(
                        "中文",
                        value=zh_text,
                        height=120,
                        key=f"card_{key_base}_{field}_zh",
                    )
                    en_value = st.text_area(
                        "English",
                        value=en_text,
                        height=140,
                        key=f"card_{key_base}_{field}_en",
                    )
                    if st.button(
                        "Save Field",
                        key=f"card_{key_base}_{field}_save",
                        width="stretch",
                    ):
                        _save_card_field(
                            paper_id=card_key,
                            card=card,
                            field=field,
                            english_value=en_value,
                            chinese_value=zh_value,
                        )
                        st.success("Field saved.")
                        st.rerun()


def _generate_bilingual_card(card: dict) -> dict:
    system_prompt = (
        "You convert ResearchPilot paper cards into bilingual Chinese-English JSON. "
        "Preserve factual uncertainty. Do not invent datasets, results, or claims absent from the source card."
    )
    schema = {
        "paper_id": "string",
        "title": "string",
        "problem": "English string",
        "method": "English string",
        "contribution": "English string",
        "dataset": "English string",
        "result": "English string",
        "limitation": "English string",
        "future_work": "English string",
        "relevance": "English string",
        "zh": {
            "title": "中文标题或原题名",
            "problem": "中文",
            "method": "中文",
            "contribution": "中文",
            "dataset": "中文",
            "result": "中文",
            "limitation": "中文",
            "future_work": "中文",
            "relevance": "中文",
        },
    }
    user_prompt = (
        "Return one strict JSON object matching this schema. Keep source_metadata if present.\n\n"
        f"Schema:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"Source card:\n{_compact_json(card)}"
    )
    response = chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    parsed = _extract_json_object(response)
    if not parsed:
        raise RuntimeError("Backend LLM did not return a JSON object.")
    if isinstance(card.get("source_metadata"), dict) and "source_metadata" not in parsed:
        parsed["source_metadata"] = card["source_metadata"]
    return parsed


def _workspace_fallback_answer(question: str, selected_cards: dict[str, dict]) -> str:
    if not selected_cards:
        return (
            "当前后端 LLM 未配置，且没有选择 paper cards。"
            "请先生成/选择 paper cards，或在 `.env` 配置 OpenAI-compatible 后端后进行自由对话。"
        )
    lines = [
        "# Workspace 摘要",
        "",
        "当前后端 LLM 未配置；下面是基于已选 paper cards 的确定性摘要，适合预览，不等价于完整 LLM 分析。",
        "",
        f"用户问题：{question}",
        "",
    ]
    for paper_id, card in selected_cards.items():
        lines.extend(
            [
                f"## {card.get('title', paper_id)}",
                f"- paper_id: {paper_id}",
                f"- problem: {card.get('problem', '')}",
                f"- method: {card.get('method', '')}",
                f"- contribution: {card.get('contribution', '')}",
                f"- result: {card.get('result', '')}",
                f"- limitation: {card.get('limitation', '')}",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _agent_workspace_chat_prompt(question: str, selected_cards: dict[str, dict]) -> str:
    effective_cards = selected_cards or paper_cards
    context = workspace_context_payload(
        paper_cards=effective_cards,
        watchlist=st.session_state.get("watchlist", []),
    )
    history = st.session_state.get("workspace_chat_messages", [])[-8:]
    return (
        "你是 ResearchPilot 网页端的本地科研 agent。请基于工作区上下文回答用户问题。"
        "如果用户要求报告，输出可直接预览和保存的 Markdown。"
        "请明确不确定性，不要引入上下文之外的事实。\n\n"
        f"工作区上下文：\n{_compact_json(context, limit=42000)}\n\n"
        f"最近对话：\n{_compact_json(history, limit=12000)}\n\n"
        f"用户问题：\n{question}"
    )


def _workspace_chat_answer(
    question: str,
    selected_cards: dict[str, dict],
    provider: str,
    model: str = "",
    timeout_seconds: int = 300,
) -> str:
    effective_cards = selected_cards or paper_cards
    normalized_provider = str(provider or "auto").lower()
    if normalized_provider == "auto":
        normalized_provider = "backend .env" if _backend_llm_configured() else "queue"
    if normalized_provider == "deterministic":
        return _workspace_fallback_answer(question, effective_cards)
    if normalized_provider in {"codex", "opencode", "queue"}:
        bridge_result = _run_or_queue_agent_generation(
            provider=normalized_provider,
            task_type="workspace_chat",
            prompt=_agent_workspace_chat_prompt(question, effective_cards),
            model=model,
            timeout_seconds=timeout_seconds,
            payload={"question": question},
        )
        return bridge_result["output"]
    if not _backend_llm_configured():
        return _workspace_fallback_answer(question, effective_cards)

    context = workspace_context_payload(
        paper_cards=effective_cards,
        watchlist=st.session_state.get("watchlist", []),
    )

    history = st.session_state.get("workspace_chat_messages", [])[-8:]
    messages = [
        {
            "role": "system",
            "content": (
                "你是 ResearchPilot 网页端的科研工作区助手。你可以读取用户工作区上下文："
                "已保存 paper cards、已入库论文摘要、watchlist、最近 venue collection 和已保存报告。"
                "回答要基于给定上下文，明确不确定性；如果用户要求报告，输出可直接预览和保存的 Markdown。"
            ),
        },
        {
            "role": "user",
            "content": f"工作区上下文：\n{_compact_json(context, limit=36000)}",
        },
    ]
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": question})
    return chat_completion(messages=messages, temperature=0.2)


def _should_track_watch_item(item: dict) -> bool:
    item_type = str(item.get("type", "") or "").strip()
    return item_type in {"research_group", "professor", "institution"}


def _refresh_watch_item_tracking(
    item: dict,
    *,
    months: int = 6,
    max_results: int = 25,
) -> dict:
    result = track_watch_item(item, months=months, max_results=max_results)
    st.session_state["watchlist_tracking"] = load_watchlist_tracking()
    return result


def _add_tracking_paper_to_library(
    paper: dict,
    item: dict,
    *,
    download_and_ingest: bool = False,
) -> tuple[str, str | None]:
    card = paper_card_from_metadata(paper, topic=str(item.get("name", "")))
    paper_id = str(card["paper_id"])
    paper_cards[paper_id] = card
    save_paper_cards_cache(paper_cards)
    st.session_state["paper_cards"] = paper_cards

    ingested_id: str | None = None
    if download_and_ingest:
        pdf_url = str(paper.get("pdf_url", "") or "").strip()
        if not pdf_url:
            raise RuntimeError("This paper does not expose a PDF URL.")
        downloaded_path = download_pdf_from_url(pdf_url, output_dir="data/uploads")
        chunks = pipeline.ingest_pdf(downloaded_path, paper_id=paper_id)
        ingested_id = paper_id
        if chunks and paper_id in paper_cards:
            del paper_cards[paper_id]
            st.session_state["paper_cards"] = paper_cards
            save_paper_cards_cache(paper_cards)
    return paper_id, ingested_id


def _render_homepage_index(index_rows: list[dict]) -> None:
    if not index_rows:
        st.info("暂无主页索引。")
        return
    for row in index_rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", "Homepage") or "Homepage")
        kind = str(row.get("kind", "") or "")
        url = str(row.get("url", "") or "")
        if url:
            st.markdown(f"- [{label}]({url}) `{kind}`")


def _render_tracking_papers(item: dict, tracking: dict, idx: int) -> None:
    dismissed = set(map(str, tracking.get("dismissed_paper_ids", []) or []))
    papers = [paper for paper in tracking.get("papers", []) or [] if isinstance(paper, dict)]
    visible_papers = [
        paper
        for paper in papers
        if str(paper.get("paper_id") or metadata_paper_id(paper)) not in dismissed
    ]
    st.caption(
        f"tracked_at={tracking.get('tracked_at', 'never')} · "
        f"cutoff={tracking.get('cutoff_date', '')} · "
        f"visible={len(visible_papers)} / total={len(papers)}"
    )
    warnings = tracking.get("warnings", []) if isinstance(tracking.get("warnings"), list) else []
    if warnings:
        with st.expander("Tracking warnings"):
            for warning in warnings:
                st.warning(str(warning))

    with st.expander("主页 / 学术索引", expanded=True):
        _render_homepage_index(tracking.get("homepage_index", []) or homepage_index_for_watch_item(item))

    download_and_ingest = st.checkbox(
        "加入时如果有 PDF URL，同时下载并 ingest",
        value=False,
        key=f"watch_track_ingest_{idx}_{watch_item_key(item)}",
    )
    if not visible_papers:
        st.info("当前没有可展示的新论文；可能都被忽略，或 API 没有返回近 6 个月结果。")
        return

    for paper_idx, paper in enumerate(visible_papers, start=1):
        paper_id = str(paper.get("paper_id") or metadata_paper_id(paper))
        title = str(paper.get("title", paper_id))
        with st.container(border=True):
            st.markdown(f"**{paper_idx}. {title}**")
            st.caption(
                f"{paper.get('source', '')} · {paper.get('publication_date') or paper.get('year', '')} · "
                f"{paper.get('venue', '')} · id={paper_id}"
            )
            authors = paper.get("authors", []) or []
            if authors:
                st.markdown(f"**authors**: {', '.join(map(str, authors[:8]))}")
            reasons = paper.get("watch_match_reasons", []) or []
            if reasons:
                st.markdown(f"**watch match**: {', '.join(map(str, reasons[:8]))}")
            abstract = str(paper.get("abstract", "") or "").strip()
            if abstract:
                st.markdown(abstract[:900] + ("..." if len(abstract) > 900 else ""))
            link_cols = st.columns([1, 1, 1])
            source_url = str(paper.get("source_url", "") or "")
            pdf_url = str(paper.get("pdf_url", "") or "")
            if source_url:
                link_cols[0].markdown(f"[source]({source_url})")
            if pdf_url:
                link_cols[1].markdown(f"[pdf]({pdf_url})")
            if str(paper_id) in paper_cards:
                link_cols[2].success("card cached")

            action_cols = st.columns(2)
            if action_cols[0].button(
                "加入 Library + 生成 Card",
                key=f"watch_track_add_card_{idx}_{paper_idx}_{_safe_widget_key(paper_id)}",
                width="stretch",
            ):
                try:
                    card_id, ingested_id = _add_tracking_paper_to_library(
                        paper,
                        item,
                        download_and_ingest=download_and_ingest,
                    )
                    if ingested_id:
                        message = f"已入库 PDF: {ingested_id}；metadata-only card 已清理"
                    else:
                        message = f"已生成 paper card: {card_id}"
                    st.success(message)
                    st.rerun()
                except Exception as exc:
                    st.error(f"加入失败：{exc}")
            if action_cols[1].button(
                "不感兴趣，移出推荐",
                key=f"watch_track_dismiss_{idx}_{paper_idx}_{_safe_widget_key(paper_id)}",
                width="stretch",
            ):
                dismiss_watch_paper(item, paper_id)
                st.session_state["watchlist_tracking"] = load_watchlist_tracking()
                st.success("已从该关注对象的推荐页隐藏。")
                st.rerun()


tab_home, tab_discovery, tab_watchlist, tab_upload, tab_ask, tab_cards, tab_review, tab_ideas, tab_workspace_chat, tab_library = st.tabs(
    [
        "首页",
        "Research Discovery",
        "Watchlist",
        "Upload PDFs",
        "Ask Papers",
        "Paper Cards",
        "Literature Review",
        "Research Ideas",
        "Workspace Chat",
        "Current Library",
    ]
)

with tab_home:
    _render_home()


def _render_arxiv_search_panel() -> None:
    _render_section_header(
        "arXiv-only 检索",
        "只调用 arXiv 结果，适合快速查新、勾选下载和 PDF 入库。",
        "Discovery mode",
    )
    _render_workflow_strip(
        [
            ("输入方向", "用 topic、排序方式和 watchlist 优先级限定快速检索范围。"),
            ("筛选论文", "结果按相关性和关注对象匹配展示，可逐篇查看摘要与命中原因。"),
            ("下载入库", "选中 PDF 后下载到本地，并可自动进入语料库用于后续分析。"),
        ]
    )
    _render_inline_stats(
        [
            ("当前结果", len(st.session_state.get("arxiv_results", []))),
            ("已入库", len(pipeline.list_papers())),
            ("Watchlist", len(st.session_state.get("watchlist", []))),
        ]
    )
    _render_command_panel(
        "只看 arXiv",
        "开启顶部 arXiv-only 开关时，仅返回 arXiv 结果；关闭后使用会议、期刊和学术搜索聚合配置。",
        ["arXiv", "watchlist ranking", "PDF ingest"],
    )
    current_arxiv_results = st.session_state.get("arxiv_results", [])
    search_topic_input = st.text_input(
        "Research topic",
        value=st.session_state.get("arxiv_topic", ""),
        key="arxiv_topic_input",
    )
    arxiv_max_results = st.slider(
        "Max results",
        min_value=3,
        max_value=20,
        value=5,
        key="arxiv_max_results",
    )
    arxiv_sort_by = st.selectbox(
        "Sort by",
        options=["relevance", "submitted_date"],
        index=0,
        key="arxiv_sort_by",
    )
    prioritize_watchlist_matches = st.checkbox(
        "Prioritize watchlist matches",
        value=True,
        key="arxiv_prioritize_watchlist_matches",
    )

    if st.button("Search arXiv", width="stretch", key="search_arxiv_button"):
        topic = search_topic_input.strip()
        if not topic:
            st.warning("Please enter a research topic.")
        else:
            try:
                with st.spinner("Searching arXiv..."):
                    results = search_arxiv_papers(
                        topic,
                        max_results=arxiv_max_results,
                        sort_by=arxiv_sort_by,
                    )
                try:
                    current_watchlist = load_watchlist()
                    st.session_state["watchlist"] = current_watchlist
                except Exception as exc:
                    current_watchlist = st.session_state.get("watchlist", [])
                    st.warning(f"Failed to reload watchlist from disk: {exc}")

                ranked_results = rank_papers_by_watchlist(
                    results,
                    current_watchlist,
                    prioritize=prioritize_watchlist_matches,
                )

                st.session_state["arxiv_results"] = ranked_results
                st.session_state["arxiv_topic"] = topic
                current_arxiv_results = ranked_results
                if ranked_results:
                    st.success(f"Found {len(ranked_results)} arXiv papers.")
                else:
                    st.info("No arXiv papers found for this topic.")
            except Exception as exc:
                st.error(f"Search failed: {exc}")

    if current_arxiv_results:
        st.caption(f'Latest topic: "{st.session_state.get("arxiv_topic", "")}"')
        st.subheader("Search Results")

        for rank, paper in enumerate(current_arxiv_results, start=1):
            paper_title = str(paper.get("title", ""))
            watch_score = float(paper.get("watchlist_score", 0.0))
            if watch_score > 0:
                expander_title = f"{rank}. ⭐ score={watch_score:.1f} | {paper_title}"
            else:
                expander_title = f"{rank}. {paper_title}"
            with st.expander(expander_title):
                st.markdown(f"**rank**: {rank}")
                st.markdown(f"**title**: {paper_title}")
                st.markdown(f"**authors**: {', '.join(paper.get('authors', []))}")
                st.markdown(f"**published**: {paper.get('published', '')}")
                st.markdown(
                    f"**primary_category**: {paper.get('primary_category', '')}"
                )
                st.markdown(f"**summary**: {paper.get('summary', '')}")
                st.markdown(f"**pdf_url**: {paper.get('pdf_url', '')}")
                matched_items = paper.get("matched_watch_items", []) or []
                reasons = paper.get("watchlist_reasons", []) or []
                st.markdown(f"**Watchlist score**: {watch_score:.2f}")
                if watch_score > 0:
                    st.markdown(f"**Matched watch items**: {matched_items}")
                    st.markdown("**Match reasons**:")
                    for reason in reasons:
                        st.markdown(f"- {reason}")
                else:
                    st.markdown("No watchlist match.")
                st.checkbox(
                    "Select this paper",
                    key=_arxiv_selection_key(paper, rank),
                )

        st.divider()
        auto_ingest = st.checkbox(
            "Auto ingest downloaded PDFs",
            value=True,
            key="arxiv_auto_ingest",
        )
        if st.button(
            "Download Selected Papers",
            width="stretch",
            key="download_selected_arxiv_papers",
        ):
            selected_papers: list[dict] = []
            for rank, paper in enumerate(current_arxiv_results, start=1):
                if st.session_state.get(_arxiv_selection_key(paper, rank), False):
                    selected_papers.append(paper)

            if not selected_papers:
                st.warning("Please select at least one paper first.")
            else:
                for paper in selected_papers:
                    paper_title = str(paper.get("title", ""))
                    try:
                        downloaded_path = download_arxiv_paper(
                            paper,
                            output_dir="data/uploads",
                        )
                        st.success(
                            f"Downloaded: {paper_title}\n\nSaved to: {downloaded_path}"
                        )
                        if auto_ingest:
                            chunks = pipeline.ingest_pdf(downloaded_path)
                            ingested_paper_id = Path(downloaded_path).stem
                            if ingested_paper_id in paper_cards:
                                del paper_cards[ingested_paper_id]
                            st.success(
                                f"Ingested {ingested_paper_id}: {len(chunks)} chunks."
                            )
                    except Exception as exc:
                        st.error(f"{paper_title}: download/ingest failed. {exc}")


def _render_default_research_discovery() -> None:
    _render_section_header(
        "科研方向会议/期刊论文搜集",
        "从研究方向出发规划 CCF venue，合并 arXiv、OpenReview、OpenAlex、Semantic Scholar 与补查链接，形成可保存的 collection。",
        "Default discovery",
    )
    _render_workflow_strip(
        [
            ("规划 venue", "基于 topic、领域提示和强制 venue 生成 CCF 会议/期刊候选。"),
            ("聚合论文", "从 arXiv、OpenReview、OpenAlex、Semantic Scholar 等来源采集并按相关性过滤。"),
            ("生成资产", "把 collection 转成 metadata cards、调研报告和可保存 workspace 文档。"),
        ]
    )
    venue_plan = st.session_state.get("venue_plan")
    venue_collection = st.session_state.get("venue_collection")
    current_collection_count = 0
    if isinstance(st.session_state.get("venue_collection"), dict):
        current_collection_count = int(st.session_state["venue_collection"].get("paper_count", 0) or 0)
    _render_inline_stats(
        [
            ("已规划 venue", len((venue_plan or {}).get("venues", [])) if isinstance(venue_plan, dict) else 0),
            ("已采集论文", current_collection_count),
            ("缓存 cards", len(paper_cards)),
        ]
    )
    current_year = datetime.now().year
    default_topic = (
        st.session_state.get("venue_collection", {}) or {}
    ).get("topic", "") or st.session_state.get("arxiv_topic", "")
    venue_topic = st.text_input(
        "Research topic",
        value=str(default_topic),
        key="venue_topic_input",
        placeholder="形式化验证与大模型结合",
    )
    col_left, col_right = st.columns(2)
    with col_left:
        domain_hints = st.text_input(
            "Domain hints",
            value="ai, formal_methods",
            key="venue_domain_hints",
            help="Examples: ai, formal_methods, programming_languages, software_engineering",
        )
        forced_venues = st.text_input(
            "Force include venues",
            value="",
            key="venue_forced_venues",
            placeholder="ICLR, NeurIPS, CAV, PLDI",
        )
        years_text = st.text_input(
            "Years",
            value=f"{current_year}, {current_year - 1}",
            key="venue_years",
        )
    with col_right:
        extra_keywords = st.text_area(
            "Extra keywords",
            value="large language models\nformal verification\nformal specification\nverified code generation",
            key="venue_extra_keywords",
            height=136,
        )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        include_arxiv = st.checkbox("arXiv", value=True, key="venue_include_arxiv")
        include_journals = st.checkbox("Include journals", value=True, key="venue_include_journals")
    with col_b:
        include_openreview = st.checkbox("OpenReview", value=True, key="venue_include_openreview")
        include_openalex = st.checkbox("OpenAlex", value=True, key="venue_include_openalex")
    with col_c:
        include_semantic_scholar = st.checkbox("Semantic Scholar", value=True, key="venue_include_semantic_scholar")
        include_broad_openalex = st.checkbox("Keep broad OpenAlex hits", value=True, key="venue_include_broad_openalex")
        include_broad_semantic_scholar = st.checkbox(
            "Keep broad Semantic Scholar hits",
            value=True,
            key="venue_include_broad_semantic_scholar",
        )

    col_limits_1, col_limits_2, col_limits_3 = st.columns(3)
    with col_limits_1:
        max_venues = st.slider("Max venues", 4, 24, 12, key="venue_max_venues")
    with col_limits_2:
        max_results_per_venue = st.slider("Results per venue", 2, 30, 8, key="venue_max_results_per_venue")
    with col_limits_3:
        max_total = st.slider("Max total papers", 10, 160, 60, key="venue_max_total")
    min_relevance_score = st.slider(
        "Minimum relevance score",
        min_value=0.0,
        max_value=8.0,
        value=1.0,
        step=0.5,
        key="venue_min_relevance",
    )

    plan_col, collect_col = st.columns(2)
    if plan_col.button("Plan CCF Venues", width="stretch", key="plan_venue_collection_button"):
        topic = venue_topic.strip()
        if not topic:
            st.warning("Please enter a topic.")
        else:
            try:
                plan = plan_venue_collection(
                    topic=topic,
                    domains=_split_csv_or_lines(domain_hints),
                    keywords=_split_csv_or_lines(extra_keywords),
                    venues=_split_csv_or_lines(forced_venues),
                    include_journals=include_journals,
                    max_venues=max_venues,
                )
                st.session_state["venue_plan"] = plan
                venue_plan = plan
                st.success(f"Planned {len(plan.get('venues', []))} venues.")
            except Exception as exc:
                st.error(f"Venue planning failed: {exc}")

    if collect_col.button("Collect Papers", width="stretch", key="collect_venue_papers_button"):
        topic = venue_topic.strip()
        years = _parse_years(years_text)
        if not topic:
            st.warning("Please enter a topic.")
        elif not years:
            st.warning("Please enter at least one valid year.")
        else:
            try:
                with st.spinner("Collecting papers from arXiv, venue sources and academic search APIs..."):
                    collection = collect_venue_papers(
                        topic=topic,
                        domains=_split_csv_or_lines(domain_hints),
                        keywords=_split_csv_or_lines(extra_keywords),
                        venues=_split_csv_or_lines(forced_venues),
                        years=years,
                        include_journals=include_journals,
                        max_venues=max_venues,
                        max_results_per_venue=max_results_per_venue,
                        max_total=max_total,
                        include_arxiv=include_arxiv,
                        include_openreview=include_openreview,
                        include_openalex=include_openalex,
                        include_broad_openalex=include_broad_openalex,
                        include_semantic_scholar=include_semantic_scholar,
                        include_broad_semantic_scholar=include_broad_semantic_scholar,
                        min_relevance_score=min_relevance_score,
                    )
                LAST_VENUE_COLLECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
                LAST_VENUE_COLLECTION_PATH.write_text(
                    json.dumps(collection, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                st.session_state["venue_collection"] = collection
                st.session_state["venue_plan"] = collection.get("plan")
                venue_collection = collection
                venue_plan = collection.get("plan")
                st.success(f"Collected {collection.get('paper_count', 0)} papers.")
            except Exception as exc:
                st.error(f"Paper collection failed: {exc}")

    if venue_plan:
        st.divider()
        st.subheader("Venue Plan")
        venues = venue_plan.get("venues", []) if isinstance(venue_plan, dict) else []
        if venues:
            st.dataframe(
                [
                    {
                        "acronym": item.get("acronym", ""),
                        "name": item.get("name", ""),
                        "ccf_rank": item.get("ccf_rank", ""),
                        "field": item.get("ccf_field", ""),
                        "kind": item.get("kind", ""),
                        "domains": ", ".join(item.get("domains", [])),
                        "url": item.get("proceedings_url") or item.get("homepage", ""),
                    }
                    for item in venues
                    if isinstance(item, dict)
                ],
                width="stretch",
            )
        scholar_urls = venue_plan.get("scholar_followup_urls", []) if isinstance(venue_plan, dict) else []
        if scholar_urls:
            with st.expander("Google Scholar follow-up links"):
                for item in scholar_urls[:20]:
                    if isinstance(item, dict):
                        label = item.get("label") or item.get("venue") or "Scholar"
                        st.markdown(f"- [{label}]({item.get('url', '')})")

    rows = _collection_rows(venue_collection)
    if rows:
        st.divider()
        st.subheader("Collected Papers")
        st.dataframe(rows, width="stretch", height=420)
        st.download_button(
            "Download Collection JSON",
            data=json.dumps(venue_collection, ensure_ascii=False, indent=2),
            file_name="venue_paper_collection.json",
            mime="application/json",
            width="stretch",
            key="download_venue_collection_json",
        )

        warnings = venue_collection.get("warnings", []) if isinstance(venue_collection, dict) else []
        if warnings:
            with st.expander("Collection warnings"):
                for warning in warnings:
                    st.warning(str(warning))

        papers_for_cards = venue_collection.get("papers", []) if isinstance(venue_collection, dict) else []
        valid_indices = [idx for idx, item in enumerate(papers_for_cards) if isinstance(item, dict)]
        selected_indices = st.multiselect(
            "Select papers for metadata paper cards",
            options=valid_indices,
            format_func=lambda idx: f"{idx + 1}. {papers_for_cards[idx].get('title', '')[:110]}",
            key="venue_metadata_card_indices",
        )
        metadata_card_count = st.slider(
            "If none selected, generate cards for top N",
            min_value=1,
            max_value=min(40, len(valid_indices)),
            value=min(10, len(valid_indices)),
            key="venue_metadata_card_count",
        )
        if st.button("Generate Metadata Paper Cards", width="stretch", key="generate_metadata_cards_button"):
            chosen = selected_indices or valid_indices[:metadata_card_count]
            added = 0
            for idx in chosen:
                card = paper_card_from_metadata(
                    papers_for_cards[idx],
                    topic=str(venue_collection.get("topic", "")),
                )
                paper_cards[str(card["paper_id"])] = card
                added += 1
            save_paper_cards_cache(paper_cards)
            st.session_state["paper_cards"] = paper_cards
            st.success(f"Generated and cached {added} metadata paper cards.")

        st.divider()
        st.subheader("Research Report")
        report_focus = st.text_area(
            "Report focus",
            value=venue_topic or str(venue_collection.get("topic", "")),
            key="venue_report_focus",
            height=90,
        )
        report_provider = st.selectbox(
            "Generation provider",
            options=["auto", "backend .env", "codex", "opencode", "queue", "deterministic"],
            index=0,
            key="venue_report_provider",
            help="queue 会把 prompt 写入本地 agent_bridge/tasks；codex/opencode 会尝试直接调用本机 CLI。",
        )
        report_bridge_model = ""
        report_bridge_timeout = 300
        if report_provider in {"codex", "opencode"}:
            bridge_cols = st.columns(2)
            with bridge_cols[0]:
                report_bridge_model = st.text_input(
                    "Bridge model override",
                    value="",
                    key="venue_report_bridge_model",
                    placeholder="codex default or opencode/minimax-m2.5-free",
                )
            with bridge_cols[1]:
                report_bridge_timeout = st.slider(
                    "Bridge timeout seconds",
                    min_value=60,
                    max_value=900,
                    value=300,
                    step=60,
                    key="venue_report_bridge_timeout",
                )
        if st.button("Generate Research Report", width="stretch", key="generate_venue_report_button"):
            try:
                with st.spinner("Generating report preview..."):
                    effective_provider = report_provider
                    if report_provider == "auto":
                        effective_provider = "backend .env" if _backend_llm_configured() else "queue"
                    if effective_provider == "backend .env":
                        if not _backend_llm_configured():
                            raise RuntimeError("Backend LLM is not configured.")
                        report = _generate_backend_venue_report(venue_collection, report_focus.strip())
                    elif effective_provider == "deterministic":
                        report = deterministic_venue_report(
                            venue_collection,
                            focus=report_focus.strip(),
                            max_papers=30,
                        )
                    else:
                        bridge_result = _run_or_queue_agent_generation(
                            provider=effective_provider,
                            task_type="venue_report",
                            prompt=_agent_report_prompt(venue_collection, report_focus.strip()),
                            model=report_bridge_model,
                            timeout_seconds=report_bridge_timeout,
                            payload={"topic": venue_collection.get("topic", "")},
                        )
                        report = bridge_result["output"]
                st.session_state["venue_report_draft"] = report
                st.session_state["venue_report_editor"] = report
                st.success("Research report preview generated.")
            except Exception as exc:
                st.error(f"Report generation failed: {exc}")

    if st.session_state.get("venue_report_draft"):
        edited_report = st.text_area(
            "Report preview / editable draft",
            value=st.session_state.get("venue_report_editor", st.session_state["venue_report_draft"]),
            height=520,
            key="venue_report_editor",
        )
        st.markdown("### Rendered Preview")
        st.markdown(edited_report)
        save_col, download_col = st.columns(2)
        if save_col.button("Approve and Save Report", width="stretch", key="save_venue_report_button"):
            title = venue_topic.strip() or "venue_report"
            path = save_workspace_report(title, edited_report, kind="venue_report")
            st.success(f"Saved report to workspace: {path}")
        download_col.download_button(
            "Download Report Markdown",
            data=edited_report,
            file_name="venue_research_report.md",
            mime="text/markdown",
            width="stretch",
            key="download_venue_report_md",
        )


with tab_discovery:
    _render_section_header(
        "Research Discovery",
        "统一 topic 入口；开启 arXiv-only 时只看 arXiv，关闭后使用默认搜索配置聚合会议、期刊、arXiv、OpenReview、OpenAlex 与 Semantic Scholar。",
        "Paper discovery",
    )
    arxiv_only_mode = st.toggle(
        "只看 arXiv 结果",
        value=False,
        key="research_discovery_arxiv_only",
        help="开启：只搜索 arXiv；关闭：按默认配置从相关会议/期刊和多个学术来源聚合结果。",
    )
    if arxiv_only_mode:
        _render_arxiv_search_panel()
    else:
        _render_default_research_discovery()


with tab_watchlist:
    _render_section_header(
        "相关学者与课题组推荐",
        "结合当前 topic、最近 collection 和已有 paper cards，推荐可加入 watchlist 的学者、课题组与机构。",
        "Scholar graph",
    )
    _render_workflow_strip(
        [
            ("推荐对象", "从 topic、collection 作者和内置专家图谱生成候选学者/课题组。"),
            ("加入关注", "一键加入 watchlist，后续搜索和报告会优先考虑这些对象。"),
            ("观察趋势", "基于搜索结果汇总关注对象近期方向和论文动向。"),
        ]
    )
    _render_inline_stats(
        [
            ("当前关注", len(watchlist)),
            ("缓存 cards", len(paper_cards)),
            ("最新 topic", _current_topic_hint()),
        ]
    )
    recommendation_topic = st.text_input(
        "推荐依据 topic",
        value=_current_topic_hint(),
        key="watchlist_recommendation_topic",
    )
    recommendations = recommend_watchlist_items(
        topic=recommendation_topic,
        collection=st.session_state.get("venue_collection"),
        paper_cards=paper_cards,
        watchlist=st.session_state.get("watchlist", []),
        limit=6,
    )
    if not recommendations:
        st.info("暂无新推荐；可以先在 Research Discovery 采集一个方向的论文，或输入更具体的推荐 topic。")
    else:
        rec_cols = st.columns(3)
        for idx, rec in enumerate(recommendations):
            with rec_cols[idx % 3]:
                with st.container(border=True):
                    institution_text = " / ".join(map(str, rec.get("institutions", [])[:3]))
                    author_text = " / ".join(map(str, rec.get("authors", [])[:4]))
                    keyword_html = "".join(
                        f'<span class="rp-chip">{_escape_html(keyword)}</span>'
                        for keyword in rec.get("keywords", [])[:6]
                    )
                    st.html(
                        f"""
                        <div class="rp-window-bar" style="padding-bottom:8px;margin-bottom:12px;">
                            <div class="rp-window-dots">
                                <span class="rp-dot rp-dot-red"></span>
                                <span class="rp-dot rp-dot-amber"></span>
                                <span class="rp-dot rp-dot-green"></span>
                            </div>
                            <span class="rp-chip rp-chip-green">score={float(rec.get('score', 0.0)):.1f}</span>
                        </div>
                        <div>
                            <div class="rp-feature-kicker">{_escape_html(rec.get("type", "custom"))} · {_escape_html(rec.get("source", ""))}</div>
                            <h3 style="margin:8px 0 10px;font-size:20px;line-height:1.25;letter-spacing:0;">{_escape_html(rec.get("name", ""))}</h3>
                            <p style="margin:0;color:#5c687a;line-height:1.6;">{_escape_html(rec.get("reason", ""))}</p>
                            <div style="margin-top:12px;color:#536174;font-size:13px;line-height:1.55;">
                                <strong>机构</strong>：{_escape_html(institution_text or "未记录")}<br>
                                <strong>代表学者</strong>：{_escape_html(author_text or "未记录")}
                            </div>
                            <div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:12px;">{keyword_html}</div>
                        </div>
                        """
                    )
                    if st.button(
                        "加入 Watchlist",
                        key=f"add_recommended_watch_{idx}_{_safe_widget_key(str(rec.get('name', '')))}",
                        width="stretch",
                    ):
                        try:
                            new_watch_item = recommendation_to_watch_item(rec)
                            updated_watchlist = add_watch_item(new_watch_item)
                            st.session_state["watchlist"] = updated_watchlist
                            watchlist = updated_watchlist
                            if _should_track_watch_item(new_watch_item):
                                with st.spinner("首次追踪主页索引与近 6 个月论文..."):
                                    _refresh_watch_item_tracking(updated_watchlist[-1])
                            st.success(f"Added watch item: {rec.get('name', '')}")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Failed to add recommendation: {exc}")

    st.divider()
    st.subheader("Add Watch Item")
    with st.form("watchlist_add_form", clear_on_submit=False):
        watch_name = st.text_input("name")
        watch_type = st.selectbox(
            "type",
            options=[
                "research_group",
                "professor",
                "institution",
                "keyword_topic",
                "custom",
            ],
            index=0,
        )
        watch_authors = st.text_area(
            "authors (one per line)",
            placeholder="Monica Lam\nChristopher Potts",
        )
        watch_institutions = st.text_area(
            "institutions (one per line)",
            placeholder="Stanford University",
        )
        watch_keywords = st.text_area(
            "keywords (one per line)",
            placeholder="STORM\nRAG\nknowledge curation",
        )
        watch_homepage_urls = st.text_area(
            "homepage/profile URLs (one per line, optional)",
            placeholder="https://example.edu/lab\nhttps://scholar.google.com/citations?...",
        )
        watch_notes = st.text_area("notes")
        add_submitted = st.form_submit_button(
            "Add to Watchlist",
            width="stretch",
        )

    if add_submitted:
        try:
            updated_watchlist = add_watch_item(
                {
                    "name": watch_name,
                    "type": watch_type,
                    "authors": _split_lines(watch_authors),
                    "institutions": _split_lines(watch_institutions),
                    "keywords": _split_lines(watch_keywords),
                    "homepage_urls": _split_lines(watch_homepage_urls),
                    "notes": watch_notes,
                }
            )
            st.session_state["watchlist"] = updated_watchlist
            watchlist = updated_watchlist
            new_watch_item = updated_watchlist[-1]
            if _should_track_watch_item(new_watch_item):
                with st.spinner("首次追踪主页索引与近 6 个月论文..."):
                    _refresh_watch_item_tracking(new_watch_item)
            st.success(f"Added watch item: {watch_name.strip()}")
        except Exception as exc:
            st.error(f"Failed to add watch item: {exc}")

    st.divider()
    st.subheader("Current Watchlist")
    st.session_state["watchlist_tracking"] = load_watchlist_tracking()
    if not watchlist:
        st.info("暂无关注对象。")
    else:
        st.caption("每个关注对象以浮动卡片展示，key-value 字段可直接扫读；详情弹层保留原始 JSON、主页索引与追踪论文。")
        watch_cols = st.columns(3)
        for idx, item in enumerate(watchlist):
            with watch_cols[idx % 3]:
                _render_watch_card(item, idx)

    st.divider()
    st.subheader("Watchlist Trend Summary")
    trend_papers = list(st.session_state.get("arxiv_results") or [])
    trend_topic = str(st.session_state.get("arxiv_topic", "") or "").strip()
    if not trend_papers and isinstance(st.session_state.get("venue_collection"), dict):
        trend_collection = st.session_state["venue_collection"]
        trend_topic = str(trend_collection.get("topic", "") or trend_topic).strip()
        for paper in trend_collection.get("papers", []) or []:
            if isinstance(paper, dict):
                trend_papers.append(
                    {
                        **paper,
                        "summary": paper.get("summary") or paper.get("abstract", ""),
                    }
                )
    if not trend_papers:
        st.info("请先在 Research Discovery 中搜索或采集论文。")
    else:
        if st.button(
            "Summarize Watchlist Trends",
            width="stretch",
            key="summarize_watchlist_trends_button",
        ):
            try:
                summary = summarize_watchlist_trends(
                    papers=trend_papers,
                    watchlist=st.session_state.get("watchlist", []),
                    topic=trend_topic,
                )
                st.session_state["watchlist_trend_summary"] = summary
                watchlist_trend_summary = summary
                st.success("Watchlist trend summary generated.")
            except Exception as exc:
                st.error(f"Failed to summarize watchlist trends: {exc}")

        if watchlist_trend_summary:
            st.markdown(watchlist_trend_summary)
            st.download_button(
                "Download Watchlist Trend Summary",
                data=watchlist_trend_summary,
                file_name="watchlist_trend_summary.md",
                mime="text/markdown",
                width="stretch",
                key="download_watchlist_trend_summary",
            )

with tab_upload:
    _render_section_header(
        "上传与解析本地 PDF",
        "将已有论文放入本地语料库，用于问答、paper card 生成、综述和引用验证。",
        "Local library",
    )
    _render_workflow_strip(
        [
            ("选择 PDF", "上传一个或多个论文文件，文件会保存在本地 workspace。"),
            ("解析切块", "提取文本、页码和 chunks，写入检索索引。"),
            ("进入分析", "入库后可生成 paper card、RAG 问答和综述验证。"),
        ]
    )
    _render_inline_stats(
        [
            ("上传目录", "data/uploads"),
            ("已入库", len(pipeline.list_papers())),
            ("缓存 cards", len(paper_cards)),
        ]
    )
    st.caption("Uploaded files are saved to: ./data/uploads")
    uploaded_files = st.file_uploader(
        "Select one or more PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if st.button("Ingest PDFs", width="stretch"):
        if not uploaded_files:
            st.warning("Please upload at least one PDF file first.")
        else:
            for uploaded_file in uploaded_files:
                try:
                    target_path = UPLOAD_DIR / uploaded_file.name
                    target_path.write_bytes(uploaded_file.getbuffer())
                    chunks = pipeline.ingest_pdf(str(target_path))
                    ingested_paper_id = target_path.stem
                    if ingested_paper_id in paper_cards:
                        # Reset cached card when the paper is re-ingested.
                        del paper_cards[ingested_paper_id]
                    st.success(
                        f"{uploaded_file.name}: ingested {len(chunks)} chunks."
                    )
                except Exception as exc:
                    st.error(f"{uploaded_file.name}: ingest failed. {exc}")

with tab_ask:
    _render_section_header(
        "基于已入库论文问答",
        "从本地 PDF chunks 中检索证据，再回答问题并展示证据片段。",
        "Evidence QA",
    )
    _render_workflow_strip(
        [
            ("提出问题", "针对已入库论文输入具体问题或比较请求。"),
            ("检索证据", "从本地 chunks 中按 top-k 找到相关片段并保留来源。"),
            ("生成回答", "输出答案并展示证据，便于核对和继续追问。"),
        ]
    )
    papers = pipeline.list_papers()
    _render_inline_stats(
        [
            ("已入库", len(papers)),
            ("默认证据", "top-k 8"),
            ("可用 cards", len(paper_cards)),
        ]
    )
    if not papers:
        st.info("No papers ingested yet. Please upload PDFs first.")

    question = st.text_input("Question")
    top_k = st.slider("Top-k evidence chunks", min_value=3, max_value=12, value=8)

    if st.button("Ask", width="stretch"):
        if not papers:
            st.warning("Please ingest at least one PDF before asking questions.")
        elif not question.strip():
            st.warning("Please enter a question.")
        else:
            try:
                with st.spinner("Retrieving evidence and generating answer..."):
                    result = pipeline.ask(question.strip(), top_k=top_k)

                answer = result.get("answer", "")
                evidence = result.get("evidence", [])

                st.subheader("Answer")
                st.write(answer)

                st.subheader("Evidence Chunks")
                if not evidence:
                    st.info("No evidence retrieved.")
                else:
                    for item in evidence:
                        rank = item.get("rank", "")
                        paper_id = item.get("paper_id", "")
                        page = item.get("page", "")
                        score = float(item.get("score", 0.0))
                        title = (
                            f"E{rank} | paper_id={paper_id} | "
                            f"page={page} | score={score:.4f}"
                        )
                        with st.expander(title):
                            st.write(item.get("text", ""))
            except Exception as exc:
                st.error(f"RAG QA failed: {exc}")

with tab_cards:
    _render_section_header(
        "Paper Cards 与 Comparison Table",
        "生成、编辑和双语化论文卡片；卡片内容会写回缓存，并自动汇总成对比表。",
        "Paper cards",
    )
    _render_workflow_strip(
        [
            ("选择论文", "按论文标题选择 paper card，底层仍保留唯一 paper_id。"),
            ("生成/编辑卡片", "按字段维护中英双语内容，所有字段都可在卡片内编辑。"),
            ("分类与比较", "通过 label 过滤、手动/agent 标注，并自动汇总 comparison table。"),
        ]
    )
    _render_inline_stats(
        [
            ("已入库", len(pipeline.list_papers())),
            ("缓存 cards", len(paper_cards)),
            ("双语 cards", sum(1 for card in paper_cards.values() if isinstance(card, dict) and isinstance(card.get("zh"), dict))),
        ]
    )
    paper_labels = load_paper_labels()
    st.session_state["paper_labels"] = paper_labels
    st.caption("Paper card cache file: ./data/outputs/paper_cards_cache.json")
    papers = pipeline.list_papers()
    cached_paper_ids = sorted(paper_cards)
    all_selectable_papers = sorted(set(papers).union(cached_paper_ids), key=lambda paper_id: _paper_title_for_select(paper_id).lower())
    available_labels = all_paper_labels(paper_labels)
    if cached_paper_ids:
        st.caption(f"Loaded cached paper cards: {len(cached_paper_ids)}")
    if not all_selectable_papers:
        st.info("No papers ingested and no cached paper cards found yet.")
    else:
        st.html('<div class="rp-paper-select-card">')
        filter_col, select_col = st.columns([0.26, 0.74])
        label_filter = filter_col.selectbox(
            "Filter by label",
            options=["全部", "未标记"] + available_labels,
            key="paper_card_label_filter",
        )
        if label_filter == "全部":
            selectable_papers = all_selectable_papers
        elif label_filter == "未标记":
            selectable_papers = [
                paper_id for paper_id in all_selectable_papers if not labels_for_paper(paper_id, paper_labels)
            ]
        else:
            selectable_papers = [
                paper_id
                for paper_id in all_selectable_papers
                if label_filter in labels_for_paper(paper_id, paper_labels)
            ]
        if not selectable_papers:
            st.info("当前 label 过滤条件下没有 paper card。")
            selected_paper_id = None
        else:
            selected_paper_id = select_col.selectbox(
                "Select paper by title",
                options=selectable_papers,
                format_func=_paper_option_label,
                key="paper_card_selected_paper",
            )
            st.caption(f"Selected paper_id: `{selected_paper_id}`")
            st.html(
                f"""
                <div class="rp-label-row" style="margin:8px 0 0;">
                    <span class="rp-chip">Labels</span>
                    {_render_chips(labels_for_paper(selected_paper_id, paper_labels))}
                </div>
                """
            )
        st.html("</div>")

        st.subheader("Library Labels")
        with st.container(border=True):
            if selected_paper_id:
                single_label_col, batch_label_col = st.columns(2)
                with single_label_col:
                    st.markdown("#### 单篇标注")
                    current_labels = labels_for_paper(selected_paper_id, paper_labels)
                    selected_existing_labels = st.multiselect(
                        "Existing labels",
                        options=available_labels,
                        default=[label for label in current_labels if label in available_labels],
                        key=f"single_existing_labels_{_safe_widget_key(selected_paper_id)}",
                    )
                    new_labels_text = st.text_input(
                        "New labels",
                        value="",
                        key=f"single_new_labels_{_safe_widget_key(selected_paper_id)}",
                        placeholder="formal specs, verified codegen",
                    )
                    action_cols = st.columns(2)
                    if action_cols[0].button("Save Labels", width="stretch", key=f"save_labels_{_safe_widget_key(selected_paper_id)}"):
                        combined = selected_existing_labels + normalize_labels(new_labels_text)
                        paper_labels = set_paper_labels(selected_paper_id, combined, labels=paper_labels)
                        st.session_state["paper_labels"] = paper_labels
                        st.success("Labels saved.")
                        st.rerun()
                    if action_cols[1].button("Clear Labels", width="stretch", key=f"clear_labels_{_safe_widget_key(selected_paper_id)}"):
                        paper_labels = set_paper_labels(selected_paper_id, [], labels=paper_labels)
                        st.session_state["paper_labels"] = paper_labels
                        st.success("Labels cleared.")
                        st.rerun()
                with batch_label_col:
                    st.markdown("#### 批量标注")
                    batch_targets = st.multiselect(
                        "Papers",
                        options=all_selectable_papers,
                        default=[],
                        format_func=_paper_option_label,
                        key="batch_label_targets",
                    )
                    batch_existing_labels = st.multiselect(
                        "Batch existing labels",
                        options=available_labels,
                        key="batch_existing_labels",
                    )
                    batch_new_labels_text = st.text_input(
                        "Batch new labels",
                        value="",
                        key="batch_new_labels",
                        placeholder="new label, another label",
                    )
                    batch_overwrite = st.checkbox("Overwrite existing labels", value=False, key="batch_label_overwrite")
                    batch_only_unlabeled = st.checkbox("Only apply to unlabeled papers", value=False, key="batch_only_unlabeled")
                    if st.button("Apply Batch Labels", width="stretch", key="apply_batch_labels"):
                        if not batch_targets:
                            st.warning("Please select at least one paper.")
                        else:
                            combined = batch_existing_labels + normalize_labels(batch_new_labels_text)
                            if not combined:
                                st.warning("Please choose or enter at least one label.")
                            else:
                                paper_labels = add_labels_to_papers(
                                    batch_targets,
                                    combined,
                                    overwrite=batch_overwrite,
                                    only_unlabeled=batch_only_unlabeled,
                                    labels=paper_labels,
                                )
                                st.session_state["paper_labels"] = paper_labels
                                st.success(f"Applied labels to {len(batch_targets)} selected papers.")
                                st.rerun()

            st.divider()
            st.markdown("#### Agent-assisted Labeling")
            unlabeled_papers = [
                paper_id for paper_id in all_selectable_papers if not labels_for_paper(paper_id, paper_labels)
            ]
            agent_cols = st.columns([0.28, 0.24, 0.24, 0.24])
            with agent_cols[0]:
                agent_provider = st.selectbox(
                    "Agent provider",
                    options=["queue", "codex", "opencode"],
                    index=0,
                    key="paper_label_agent_provider",
                )
            with agent_cols[1]:
                agent_target_mode = st.selectbox(
                    "Target",
                    options=["Selected unlabeled", "All unlabeled"],
                    index=0,
                    key="paper_label_agent_target_mode",
                )
            with agent_cols[2]:
                agent_model = st.text_input(
                    "Model override",
                    value="",
                    key="paper_label_agent_model",
                    placeholder="optional",
                )
            with agent_cols[3]:
                agent_timeout = st.slider(
                    "Timeout",
                    min_value=60,
                    max_value=900,
                    value=300,
                    step=60,
                    key="paper_label_agent_timeout",
                )
            agent_selected_targets = st.multiselect(
                "Selected unlabeled papers for agent",
                options=unlabeled_papers,
                default=unlabeled_papers[: min(8, len(unlabeled_papers))],
                format_func=_paper_option_label,
                key="paper_label_agent_targets",
                disabled=agent_target_mode == "All unlabeled",
            )
            if st.button("Run / Queue Agent Labeling", width="stretch", key="run_agent_labeling"):
                target_ids = unlabeled_papers if agent_target_mode == "All unlabeled" else agent_selected_targets
                if not target_ids:
                    st.warning("没有未标注论文可交给 agent。")
                else:
                    prompt = _agent_label_prompt(target_ids, available_labels)
                    try:
                        result = _run_or_queue_agent_generation(
                            provider=agent_provider,
                            task_type="paper_label_assignment",
                            prompt=prompt,
                            model=agent_model,
                            timeout_seconds=agent_timeout,
                            payload={"paper_ids": target_ids, "existing_labels": available_labels},
                        )
                        if result["mode"] == "queued":
                            st.info(result["output"])
                        else:
                            applied, skipped = _apply_agent_label_assignments(result["output"])
                            st.success(f"Agent labels applied: {applied}")
                            if skipped:
                                st.caption("Skipped: " + "; ".join(skipped[:8]))
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Agent labeling failed: {exc}")

        if not selected_paper_id:
            current_card = None
            selected_is_ingested = False
        else:
            selected_is_ingested = selected_paper_id in papers
        if not selected_is_ingested:
            st.info("This paper card is loaded from cache; ingest the PDF first if you want to regenerate it from full text.")
        if st.button("Generate Paper Card", width="stretch", disabled=not selected_is_ingested):
            try:
                card = pipeline.build_paper_card(selected_paper_id)
                paper_cards[selected_paper_id] = card
                save_paper_cards_cache(paper_cards)
                st.success(f"Paper card generated for: {selected_paper_id}")
            except Exception as exc:
                st.error(f"Paper card generation failed: {exc}")

        current_card = paper_cards.get(selected_paper_id)
        if current_card is None:
            st.info("No paper card generated for this paper yet.")
        else:
            if isinstance(current_card, dict):
                card_provider = st.selectbox(
                    "Bilingual generation provider",
                    options=["backend .env", "codex", "opencode", "queue"],
                    index=1,
                    key=f"bilingual_provider_{_safe_widget_key(selected_paper_id)}",
                    help="codex/opencode 通过本地 agent bridge 生成；queue 只创建 prompt 文件。",
                )
                action_col_1, action_col_2 = st.columns(2)
                if action_col_1.button(
                    "Generate Bilingual Version",
                    width="stretch",
                    key=f"generate_bilingual_card_{selected_paper_id}",
                ):
                    try:
                        with st.spinner("Generating bilingual paper card..."):
                            if card_provider == "backend .env":
                                if not _backend_llm_configured():
                                    raise RuntimeError("Backend LLM is not configured.")
                                bilingual_card = _generate_bilingual_card(current_card)
                            else:
                                bridge_result = _run_or_queue_agent_generation(
                                    provider=card_provider,
                                    task_type="bilingual_paper_card",
                                    prompt=_agent_bilingual_card_prompt(current_card),
                                    timeout_seconds=300,
                                    payload={"paper_id": selected_paper_id},
                                )
                                if bridge_result["mode"] == "queued":
                                    st.info(bridge_result["output"])
                                    bilingual_card = None
                                else:
                                    bilingual_card = _extract_json_object(bridge_result["output"])
                                    if not bilingual_card:
                                        raise RuntimeError("Agent bridge did not return a JSON object.")
                            if bilingual_card is not None:
                                paper_cards[selected_paper_id] = bilingual_card
                                save_paper_cards_cache(paper_cards)
                                current_card = bilingual_card
                                st.success("Bilingual paper card generated and cached.")
                    except Exception as exc:
                        st.error(f"Bilingual card generation failed: {exc}")
                action_col_2.download_button(
                    "Download Card JSON",
                    data=json.dumps(current_card, ensure_ascii=False, indent=2),
                    file_name=f"{selected_paper_id.replace('/', '_')}_paper_card.json",
                    mime="application/json",
                    width="stretch",
                    key=f"download_card_json_{selected_paper_id}",
                )

                st.subheader("Paper Card")
                _render_paper_card(current_card, selected_paper_id)

                with st.expander("Raw JSON"):
                    st.json(current_card)

                if "raw" in current_card or "parse_error" in current_card:
                    warning_msg = (
                        f"raw={current_card.get('raw', '')}\n\n"
                        f"parse_error={current_card.get('parse_error', '')}"
                    )
                    st.warning(warning_msg)
            else:
                st.write(current_card)

    st.divider()
    st.subheader("Comparison Table")
    if len(paper_cards) >= 1:
        comparison_scope = st.selectbox(
            "Comparison scope",
            options=["All cached cards", "Current label filter"],
            index=0,
            key="comparison_table_scope",
        )
        if comparison_scope == "Current label filter" and "selectable_papers" in locals():
            comparison_cards = {
                paper_id: paper_cards[paper_id]
                for paper_id in selectable_papers
                if paper_id in paper_cards
            }
        else:
            comparison_cards = paper_cards
        comparison_df = build_comparison_table(comparison_cards)
        if "paper_id" in comparison_df.columns:
            comparison_df.insert(
                1,
                "labels",
                comparison_df["paper_id"].map(lambda paper_id: ", ".join(labels_for_paper(str(paper_id), paper_labels))),
            )
        st.dataframe(comparison_df, width="stretch")
        csv_data = comparison_df.to_csv(index=False)
        st.download_button(
            "Download CSV",
            data=csv_data,
            file_name="paper_comparison.csv",
            mime="text/csv",
            width="stretch",
            key="download_paper_comparison_csv",
        )
    else:
        st.info("Generate at least one paper card to build a comparison table.")

with tab_review:
    _render_section_header(
        "综述生成与引用验证",
        "基于 paper cards 写作综述，再逐 claim 检索证据、标记支持程度并生成保守改写版本。",
        "Literature review",
    )
    _render_workflow_strip(
        [
            ("生成综述", "基于 paper cards 和主题生成初稿。"),
            ("验证 claim", "逐条检索证据，标记 supported / weak / unsupported。"),
            ("保守改写", "根据验证结果生成更稳健的综述版本并可比较差异。"),
        ]
    )
    _render_inline_stats(
        [
            ("Paper cards", len(paper_cards)),
            ("Review versions", len(review_versions)),
            ("Verified claims", len(st.session_state.get("claim_verification", []))),
        ]
    )
    if len(paper_cards) < 1:
        st.info("Generate paper cards first.")
    else:
        topic = st.text_input("Research topic", key="literature_review_topic")
        if st.button("Generate Literature Review", width="stretch"):
            if not topic.strip():
                st.warning("Please enter a research topic.")
            else:
                try:
                    with st.spinner("Generating literature review..."):
                        generated_review = pipeline.write_literature_review(
                            topic=topic.strip(),
                            paper_cards=paper_cards,
                        )
                    st.session_state["literature_review"] = generated_review
                    st.session_state["review_topic"] = topic.strip()
                    st.session_state["claim_verification"] = []
                    st.session_state["revised_literature_review"] = ""
                    st.session_state["review_versions"] = [
                        {
                            "label": "v0 Original",
                            "text": generated_review,
                            "verification": None,
                            "source": "generated",
                            "parent": None,
                        }
                    ]
                    st.session_state["active_review_version"] = 0
                    st.session_state["current_review_version_idx"] = 0
                    literature_review = generated_review
                    claim_verification = []
                    revised_literature_review = ""
                    review_versions = st.session_state["review_versions"]
                    active_review_version = 0
                    st.success("Literature review generated.")
                except Exception as exc:
                    st.error(f"Literature review generation failed: {exc}")

        if not review_versions and literature_review:
            st.session_state["review_versions"] = [
                {
                    "label": "v0 Original",
                    "text": literature_review,
                    "verification": None,
                    "source": "generated",
                    "parent": None,
                }
            ]
            st.session_state["active_review_version"] = 0
            st.session_state["current_review_version_idx"] = 0
            review_versions = st.session_state["review_versions"]
            active_review_version = 0

        if review_versions:
            st.divider()
            st.subheader("Review Versions")

            pending_review_idx = st.session_state.get("pending_active_review_version")
            if (
                isinstance(pending_review_idx, int)
                and 0 <= pending_review_idx < len(review_versions)
            ):
                st.session_state["active_review_version"] = pending_review_idx
                st.session_state["current_review_version_idx"] = pending_review_idx
            st.session_state["pending_active_review_version"] = None
            active_review_version = st.session_state["active_review_version"]

            max_idx = len(review_versions) - 1
            default_idx = (
                active_review_version
                if isinstance(active_review_version, int)
                and 0 <= active_review_version <= max_idx
                else max_idx
            )
            if (
                "current_review_version_idx" not in st.session_state
                or not isinstance(st.session_state["current_review_version_idx"], int)
                or not 0 <= st.session_state["current_review_version_idx"] <= max_idx
            ):
                st.session_state["current_review_version_idx"] = default_idx
            selected_idx = st.selectbox(
                "Current review version",
                options=list(range(len(review_versions))),
                format_func=lambda i: review_versions[i]["label"],
                key="current_review_version_idx",
            )
            st.session_state["active_review_version"] = selected_idx
            active_review_version = selected_idx

            current_version = review_versions[selected_idx]
            current_label = str(current_version.get("label", f"v{selected_idx}"))
            current_text = str(current_version.get("text", ""))
            current_verification = current_version.get("verification")

            st.caption(f"Current version: {current_label}")
            st.markdown(current_text)

            if selected_idx == 0:
                st.download_button(
                    "Download Original Literature Review",
                    data=current_text,
                    file_name="literature_review.md",
                    mime="text/markdown",
                    width="stretch",
                    key="download_original_review_current_version",
                )
            elif selected_idx == len(review_versions) - 1 and revised_literature_review:
                st.download_button(
                    "Download Revised Literature Review",
                    data=revised_literature_review,
                    file_name="revised_literature_review.md",
                    mime="text/markdown",
                    width="stretch",
                    key="download_revised_review_current_version",
                )
            else:
                st.download_button(
                    "Download Current Review Version",
                    data=current_text,
                    file_name=f"review_{current_label.replace(' ', '_')}.md",
                    mime="text/markdown",
                    width="stretch",
                    key=f"download_current_review_version_{selected_idx}",
                )

            st.divider()
            st.subheader("Claim-level Citation Verification")
            verify_top_k = st.slider(
                "Evidence chunks per claim",
                min_value=2,
                max_value=6,
                value=5,
            )
            verification_mode = st.selectbox(
                "Verification mode",
                options=["balanced", "strict", "lenient"],
                index=0,
            )
            source_first = st.checkbox(
                "Use source-aware evidence retrieval",
                value=True,
            )
            source_only_when_available = st.checkbox(
                "Use source-only evidence when source is available",
                value=True,
            )
            diversify_evidence = st.checkbox(
                "Diversify evidence across papers",
                value=True,
            )
            max_per_paper = 2
            if diversify_evidence:
                max_per_paper = st.slider(
                    "Max evidence chunks per paper",
                    min_value=1,
                    max_value=3,
                    value=2,
                )
                st.caption(
                    "This limit is used for diverse retrieval or multiple-source claims. "
                    "If source-only mode matches a single source paper, the verifier will "
                    "use only that source paper and may take up to Evidence chunks per claim from it."
                )
            st.caption(f"Current verification mode: {verification_mode}")
            if st.button("Verify Claims", width="stretch"):
                try:
                    with st.spinner("Verifying claims..."):
                        results = pipeline.verify_literature_review(
                            current_text,
                            top_k=verify_top_k,
                            verification_mode=verification_mode,
                            diversify_evidence=diversify_evidence,
                            max_per_paper=max_per_paper,
                            source_first=source_first,
                            source_only_when_available=source_only_when_available,
                            paper_cards=st.session_state.get("paper_cards", {}),
                        )
                    review_versions[selected_idx]["verification"] = results
                    st.session_state["review_versions"] = review_versions
                    st.session_state["active_review_version"] = selected_idx
                    st.session_state["claim_verification"] = results
                    st.session_state["revised_literature_review"] = ""
                    claim_verification = results
                    revised_literature_review = ""
                    current_verification = results
                    st.success("Claim verification completed.")
                except Exception as exc:
                    st.error(f"Claim verification failed: {exc}")

            if not current_verification:
                st.info("This version has not been verified yet.")
            else:
                supported_count = sum(
                    1
                    for item in current_verification
                    if item.get("status") == "supported"
                )
                weakly_supported_count = sum(
                    1
                    for item in current_verification
                    if item.get("status") == "weakly_supported"
                )
                unsupported_count = sum(
                    1
                    for item in current_verification
                    if item.get("status") == "unsupported"
                )
                st.markdown(
                    f"- supported: {supported_count}\n"
                    f"- weakly_supported: {weakly_supported_count}\n"
                    f"- unsupported: {unsupported_count}"
                )

                for item in current_verification:
                    claim_text = str(item.get("claim", ""))
                    status = str(item.get("status", ""))
                    title = f"[{status}] {claim_text[:80]}"
                    with st.expander(title):
                        st.markdown(f"**status**: {status}")
                        st.markdown(f"**reason**: {item.get('reason', '')}")
                        st.markdown(
                            f"**best_evidence**: {item.get('best_evidence', [])}"
                        )
                        retrieval_meta = item.get("evidence_retrieval_meta", {}) or {}
                        st.markdown("**Evidence retrieval meta**")
                        st.markdown(
                            f"**source_hints**: {retrieval_meta.get('source_hints', [])}"
                        )
                        st.markdown(
                            "**matched_source_paper_ids**: "
                            f"{retrieval_meta.get('matched_source_paper_ids', [])}"
                        )
                        st.markdown(
                            "**matched_source_titles**: "
                            f"{retrieval_meta.get('matched_source_titles', [])}"
                        )
                        st.markdown(
                            "**source_match_failed**: "
                            f"{retrieval_meta.get('source_match_failed', False)}"
                        )
                        st.markdown(
                            "**source_match_confidence**: "
                            f"{retrieval_meta.get('source_match_confidence', None)}"
                        )
                        st.markdown(
                            f"**source_first**: {retrieval_meta.get('source_first', False)}"
                        )
                        st.markdown(
                            "**source_only_when_available**: "
                            f"{retrieval_meta.get('source_only_when_available', False)}"
                        )
                        st.markdown(
                            "**source_only_effective**: "
                            f"{retrieval_meta.get('source_only_effective', False)}"
                        )
                        st.markdown(
                            "**single_source_mode**: "
                            f"{retrieval_meta.get('single_source_mode', False)}"
                        )
                        st.markdown(
                            "**diversify_evidence**: "
                            f"{retrieval_meta.get('diversify_evidence', False)}"
                        )
                        if (
                            retrieval_meta.get("source_hints")
                            and retrieval_meta.get("source_match_failed", False)
                        ):
                            st.warning(
                                "Source hint was found but could not be confidently matched "
                                "to an ingested paper. Falling back to diverse retrieval."
                            )
                        suggested_rewrite = str(
                            item.get("suggested_rewrite", "")
                        ).strip()
                        if suggested_rewrite:
                            st.markdown("**Suggested conservative rewrite**")
                            st.info(suggested_rewrite)
                        evidence_list = item.get("evidence", []) or []
                        if not evidence_list:
                            st.info("No evidence.")
                        else:
                            source_counts: dict[str, int] = {}
                            for ev in evidence_list:
                                pid = str(ev.get("paper_id", "") or "unknown")
                                source_counts[pid] = source_counts.get(pid, 0) + 1
                            st.markdown("**Evidence source coverage:**")
                            for pid, count in source_counts.items():
                                st.markdown(f"- {pid}: {count} chunks")

                            for idx, ev in enumerate(evidence_list, start=1):
                                paper_id = ev.get("paper_id", "")
                                page = ev.get("page", "")
                                score = float(ev.get("score", 0.0))
                                text = ev.get("text", "")
                                st.markdown(
                                    f"**E{idx}** paper_id={paper_id}, "
                                    f"page={page}, score={score:.4f}"
                                )
                                st.write(text)
                                if idx < len(evidence_list):
                                    st.divider()

            st.divider()
            st.subheader("Revised Literature Review")
            if st.button("Generate Revised Review", width="stretch"):
                current_verification = review_versions[selected_idx].get("verification")
                if not current_verification:
                    st.warning("Please verify this version before generating a revised review.")
                else:
                    try:
                        with st.spinner("Generating revised literature review..."):
                            revised = pipeline.rewrite_literature_review(
                                current_text,
                                current_verification,
                            )
                        next_idx = len(review_versions)
                        review_versions.append(
                            {
                                "label": f"v{next_idx} Revised",
                                "text": revised,
                                "verification": None,
                                "source": "revised",
                                "parent": selected_idx,
                            }
                        )
                        st.session_state["review_versions"] = review_versions
                        st.session_state["active_review_version"] = next_idx
                        st.session_state["pending_active_review_version"] = next_idx
                        st.session_state["revised_literature_review"] = revised
                        revised_literature_review = revised
                        st.success("Revised literature review generated.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Revised review generation failed: {exc}")

            if revised_literature_review:
                st.markdown(revised_literature_review)
                st.download_button(
                    "Download Revised Literature Review",
                    data=revised_literature_review,
                    file_name="revised_literature_review.md",
                    mime="text/markdown",
                    width="stretch",
                    key="download_revised_review_latest_section",
                )

            st.divider()
            st.subheader("Compare Review Versions")
            if len(review_versions) >= 2:
                compare_options = list(range(len(review_versions)))
                left_idx = st.selectbox(
                    "Left version",
                    options=compare_options,
                    index=0,
                    format_func=lambda i: review_versions[i]["label"],
                    key="compare_left_review_idx",
                )
                right_idx = st.selectbox(
                    "Right version",
                    options=compare_options,
                    index=len(review_versions) - 1,
                    format_func=lambda i: review_versions[i]["label"],
                    key="compare_right_review_idx",
                )

                left_version = review_versions[left_idx]
                right_version = review_versions[right_idx]

                left_col, right_col = st.columns(2)
                with left_col:
                    st.markdown(f"### {left_version['label']}")
                    st.markdown(str(left_version.get("text", "")))
                with right_col:
                    st.markdown(f"### {right_version['label']}")
                    st.markdown(str(right_version.get("text", "")))

                diff_text = make_unified_diff(
                    str(left_version.get("text", "")),
                    str(right_version.get("text", "")),
                    old_label=str(left_version.get("label", "old")),
                    new_label=str(right_version.get("label", "new")),
                )
                with st.expander("Text diff"):
                    st.code(diff_text, language="diff")
            else:
                st.info("Need at least two versions to compare.")

with tab_ideas:
    _render_section_header(
        "研究想法生成",
        "把已有 card、综述和验证结果转成下一步可探索的问题、方法和实验路线。",
        "Research ideas",
    )
    _render_workflow_strip(
        [
            ("读取上下文", "综合 paper cards、原始综述、修订综述和 claim verification。"),
            ("生成候选", "按主题输出多个研究问题、方法路径和实验建议。"),
            ("导出沉淀", "将想法保存或下载，作为下一轮调研和实验规划的输入。"),
        ]
    )
    _render_inline_stats(
        [
            ("Paper cards", len(paper_cards)),
            ("有综述", "是" if st.session_state.get("literature_review", "").strip() else "否"),
            ("有验证", "是" if st.session_state.get("claim_verification") else "否"),
        ]
    )
    if not paper_cards:
        st.info("Generate paper cards first.")
    else:
        has_original_review = bool(st.session_state.get("literature_review", "").strip())
        has_revised_review = bool(
            st.session_state.get("revised_literature_review", "").strip()
        )
        has_claim_verification = bool(st.session_state.get("claim_verification"))

        st.markdown(
            f"- paper cards: {len(paper_cards)}\n"
            f"- original review exists: {has_original_review}\n"
            f"- revised review exists: {has_revised_review}\n"
            f"- claim verification exists: {has_claim_verification}"
        )

        fallback_topic = (
            str(st.session_state.get("review_topic", "")).strip()
            or str(st.session_state.get("arxiv_topic", "")).strip()
        )
        if "research_ideas_topic" not in st.session_state:
            st.session_state["research_ideas_topic"] = fallback_topic
        elif not str(st.session_state["research_ideas_topic"]).strip() and fallback_topic:
            st.session_state["research_ideas_topic"] = fallback_topic

        topic_input = st.text_input(
            "Research topic",
            key="research_ideas_topic",
        )
        num_ideas = st.slider(
            "Number of ideas",
            min_value=3,
            max_value=8,
            value=5,
            key="research_ideas_count",
        )

        if st.button(
            "Generate Research Ideas",
            width="stretch",
            key="generate_research_ideas_button",
        ):
            try:
                with st.spinner("Generating research ideas..."):
                    ideas = pipeline.generate_research_ideas(
                        topic=topic_input.strip() or None,
                        paper_cards=st.session_state["paper_cards"],
                        literature_review=st.session_state.get("literature_review"),
                        revised_literature_review=st.session_state.get(
                            "revised_literature_review"
                        ),
                        claim_verification=st.session_state.get("claim_verification"),
                        num_ideas=num_ideas,
                    )
                st.session_state["research_ideas"] = ideas
                research_ideas = ideas
                st.success("Research ideas generated.")
            except Exception as exc:
                st.error(f"Research idea generation failed: {exc}")

        if research_ideas:
            st.markdown(research_ideas)
            st.download_button(
                "Download Research Ideas",
                data=research_ideas,
                file_name="research_ideas.md",
                mime="text/markdown",
                width="stretch",
                key="download_research_ideas_markdown",
            )

with tab_workspace_chat:
    _render_section_header(
        "Workspace Chat",
        "LLM 可以读取当前工作区的 paper cards、入库论文、watchlist 和已保存报告，用于比较、追问和草拟报告。",
        "Agent workspace",
    )
    _render_workflow_strip(
        [
            ("选择上下文", "限定 paper cards 或让助手读取完整 workspace。"),
            ("委托生成", "可走 backend .env、Codex、OpenCode 或本地任务队列。"),
            ("预览批准", "回答和报告都先进入可编辑预览，再保存到 workspace。"),
        ]
    )
    bridge_status = agent_bridge_status()
    context_payload = workspace_context_payload(
        paper_cards=paper_cards,
        watchlist=st.session_state.get("watchlist", []),
    )
    metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
    metric_col_1.metric("Paper cards", len(context_payload.get("paper_cards", [])))
    metric_col_2.metric("Ingested papers", len(context_payload.get("ingested_papers", [])))
    metric_col_3.metric("Watch items", len(context_payload.get("watchlist", [])))
    metric_col_4.metric("Saved reports", len(context_payload.get("workspace_reports", [])))

    provider_cols = st.columns([0.34, 0.33, 0.33])
    with provider_cols[0]:
        workspace_provider = st.selectbox(
            "Answer provider",
            options=["auto", "backend .env", "codex", "opencode", "queue", "deterministic"],
            index=0,
            key="workspace_chat_provider",
            help="queue 会把任务写入本地 agent_bridge/tasks；codex/opencode 会尝试直接调用本机 CLI。",
        )
    with provider_cols[1]:
        workspace_model = st.text_input(
            "Bridge model override",
            value="",
            key="workspace_chat_bridge_model",
            placeholder="codex default or opencode/minimax-m2.5-free",
        )
    with provider_cols[2]:
        workspace_timeout = st.slider(
            "Bridge timeout seconds",
            min_value=60,
            max_value=900,
            value=300,
            step=60,
            key="workspace_chat_bridge_timeout",
        )
    st.caption(
        "Agent bridge: "
        f"codex={'available' if bridge_status['codex_available'] else 'missing'} · "
        f"opencode={'available' if bridge_status['opencode_available'] else 'missing'} · "
        f"tasks={bridge_status['tasks_dir']}"
    )

    selected_card_ids = st.multiselect(
        "Limit card context",
        options=sorted(paper_cards),
        default=sorted(paper_cards)[: min(8, len(paper_cards))],
        format_func=_paper_option_label,
        key="workspace_chat_selected_cards",
        help="Leave empty to let the assistant see all cached paper cards.",
    )
    selected_cards = {
        paper_id: paper_cards[paper_id]
        for paper_id in selected_card_ids
        if paper_id in paper_cards
    }

    with st.expander("Workspace context preview"):
        st.json(
            workspace_context_payload(
                paper_cards=selected_cards or paper_cards,
                watchlist=st.session_state.get("watchlist", []),
                max_cards=12,
                max_reports=5,
            )
        )

    for item in st.session_state.get("workspace_chat_messages", []):
        role = item.get("role", "assistant")
        content = str(item.get("content", ""))
        if role not in {"user", "assistant"}:
            role = "assistant"
        with st.chat_message(role):
            st.markdown(content)

    prompt = st.chat_input("Ask about saved papers, topics, watchlist, comparisons, or draft a report...")
    if prompt:
        st.session_state["workspace_chat_messages"].append(
            {"role": "user", "content": prompt}
        )
        with st.chat_message("user"):
            st.markdown(prompt)
        try:
            with st.spinner("Reading workspace context and generating response..."):
                answer = _workspace_chat_answer(
                    prompt,
                    selected_cards,
                    provider=workspace_provider,
                    model=workspace_model,
                    timeout_seconds=workspace_timeout,
                )
            st.session_state["workspace_chat_messages"].append(
                {"role": "assistant", "content": answer}
            )
            st.session_state["workspace_chat_draft"] = answer
            st.session_state["workspace_chat_editor"] = answer
            with st.chat_message("assistant"):
                st.markdown(answer)
        except Exception as exc:
            st.error(f"Workspace chat failed: {exc}")

    if st.session_state.get("workspace_chat_draft"):
        st.divider()
        st.subheader("Preview / Approve")
        edited_workspace_draft = st.text_area(
            "Editable answer or report draft",
            value=st.session_state.get(
                "workspace_chat_editor",
                st.session_state.get("workspace_chat_draft", ""),
            ),
            height=420,
            key="workspace_chat_editor",
        )
        st.markdown("### Rendered Preview")
        st.markdown(edited_workspace_draft)
        title = st.text_input(
            "Save title",
            value="workspace_chat_report",
            key="workspace_chat_save_title",
        )
        save_col, clear_col = st.columns(2)
        if save_col.button("Approve and Save to Workspace", width="stretch", key="save_workspace_chat_report"):
            path = save_workspace_report(title, edited_workspace_draft, kind="workspace_chat")
            st.success(f"Saved report to workspace: {path}")
        if clear_col.button("Clear Chat", width="stretch", key="clear_workspace_chat_button"):
            st.session_state["workspace_chat_messages"] = []
            st.session_state["workspace_chat_draft"] = ""
            st.session_state["workspace_chat_editor"] = ""
            st.rerun()

    with st.expander("Local Agent Bridge Tasks"):
        tasks = list_agent_tasks(limit=10)
        if not tasks:
            st.info("No queued or executed bridge tasks yet.")
        else:
            st.dataframe(
                [
                    {
                        "task_id": task.get("task_id", ""),
                        "type": task.get("task_type", ""),
                        "provider": task.get("provider", ""),
                        "status": task.get("status", ""),
                        "created_at": task.get("created_at", ""),
                        "prompt": task.get("prompt_path", ""),
                        "result": task.get("result_path", ""),
                    }
                    for task in tasks
                ],
                width="stretch",
            )

with tab_library:
    _render_section_header(
        "当前资料库",
        "核对本地已入库论文、缓存卡片和 workspace 报告，便于确认 agent 与网页端共享状态。",
        "Current library",
    )
    _render_workflow_strip(
        [
            ("本地论文", "查看已解析入库的 paper_id 和 card 状态。"),
            ("缓存卡片", "浏览 paper card 缓存、来源和双语覆盖情况。"),
            ("保存报告", "回看 workspace 中已批准保存的调研文档。"),
        ]
    )
    papers = pipeline.list_papers()
    paper_labels = load_paper_labels()
    st.session_state["paper_labels"] = paper_labels
    library_paper_ids = sorted(set(papers).union(paper_cards), key=lambda paper_id: _paper_title_for_select(paper_id).lower())
    available_labels = all_paper_labels(paper_labels)
    _render_inline_stats(
        [
            ("已入库", len(papers)),
            ("缓存 cards", len(paper_cards)),
            ("报告", len(list_workspace_reports(limit=50))),
            ("Labels", len(available_labels)),
        ]
    )
    st.subheader("Library Label Management")
    with st.container(border=True):
        label_filter_col, batch_col = st.columns([0.28, 0.72])
        library_label_filter = label_filter_col.selectbox(
            "View by label",
            options=["全部", "未标记"] + available_labels,
            key="library_label_filter",
        )
        with batch_col:
            library_batch_targets = st.multiselect(
                "Batch label papers",
                options=library_paper_ids,
                format_func=_paper_option_label,
                key="library_batch_label_targets",
            )
            lib_label_cols = st.columns([0.34, 0.34, 0.16, 0.16])
            with lib_label_cols[0]:
                library_existing_labels = st.multiselect(
                    "Existing labels",
                    options=available_labels,
                    key="library_existing_labels",
                )
            with lib_label_cols[1]:
                library_new_labels = st.text_input(
                    "New labels",
                    value="",
                    key="library_new_labels",
                    placeholder="verified codegen, formal specs",
                )
            with lib_label_cols[2]:
                library_overwrite = st.checkbox("Overwrite", value=False, key="library_label_overwrite")
            with lib_label_cols[3]:
                library_only_unlabeled = st.checkbox("Unlabeled only", value=True, key="library_label_only_unlabeled")
            if st.button("Apply Library Labels", width="stretch", key="apply_library_labels"):
                combined = library_existing_labels + normalize_labels(library_new_labels)
                if not library_batch_targets:
                    st.warning("Please select papers first.")
                elif not combined:
                    st.warning("Please choose or enter labels first.")
                else:
                    paper_labels = add_labels_to_papers(
                        library_batch_targets,
                        combined,
                        overwrite=library_overwrite,
                        only_unlabeled=library_only_unlabeled,
                        labels=paper_labels,
                    )
                    st.session_state["paper_labels"] = paper_labels
                    st.success("Library labels updated.")
                    st.rerun()

        if library_label_filter == "未标记":
            visible_library_ids = [paper_id for paper_id in library_paper_ids if not labels_for_paper(paper_id, paper_labels)]
        elif library_label_filter == "全部":
            visible_library_ids = library_paper_ids
        else:
            visible_library_ids = [
                paper_id for paper_id in library_paper_ids if library_label_filter in labels_for_paper(paper_id, paper_labels)
            ]
        st.dataframe(
            [
                {
                    "title": _paper_title_for_select(paper_id),
                    "paper_id": paper_id,
                    "labels": ", ".join(labels_for_paper(paper_id, paper_labels)),
                    "ingested": paper_id in papers,
                    "has_card": paper_id in paper_cards,
                }
                for paper_id in visible_library_ids
            ],
            width="stretch",
        )

    if not papers:
        st.write("No papers ingested yet.")
    else:
        st.write(f"Ingested papers: {len(papers)}")
        for paper_id in papers:
            has_card = paper_id in paper_cards
            card_status = "paper_card_ready" if has_card else "paper_card_not_generated"
            label_text = ", ".join(labels_for_paper(paper_id, paper_labels)) or "unlabeled"
            st.write(f"- {_paper_title_for_select(paper_id)} `{paper_id}` ({card_status}; labels: {label_text})")
    st.divider()
    st.subheader("Cached Paper Cards")
    if paper_cards:
        st.write(f"Cached paper cards: {len(paper_cards)}")
        st.dataframe(
            [
                {
                    "paper_id": paper_id,
                    "title": card.get("title", "") if isinstance(card, dict) else "",
                    "labels": ", ".join(labels_for_paper(paper_id, paper_labels)),
                    "has_zh": bool(isinstance(card, dict) and isinstance(card.get("zh"), dict)),
                    "source": (
                        card.get("source_metadata", {}).get("source", "")
                        if isinstance(card, dict) and isinstance(card.get("source_metadata"), dict)
                        else ""
                    ),
                }
                for paper_id, card in paper_cards.items()
            ],
            width="stretch",
        )
    else:
        st.info("No cached paper cards yet.")

    st.divider()
    st.subheader("Workspace Reports")
    reports = list_workspace_reports(limit=20)
    if not reports:
        st.info("No saved workspace reports yet.")
    else:
        for report in reports:
            with st.expander(report["name"]):
                st.caption(report["path"])
                st.markdown(report["preview"])
