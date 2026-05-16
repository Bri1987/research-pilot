from pathlib import Path
from datetime import datetime
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
from researchpilot.search.arxiv_search import search_arxiv_papers
from researchpilot.storage.corpus_store import load_paper_cards_cache
from researchpilot.storage.corpus_store import save_paper_cards_cache
from researchpilot.watchlist.watchlist_ranker import rank_papers_by_watchlist
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
st.title("ResearchPilot")
st.html(
    """
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 14px;
        border-color: rgba(148, 163, 184, 0.34);
        background: rgba(255, 255, 255, 0.72);
        box-shadow: 0 18px 42px rgba(15, 23, 42, 0.08);
    }
    div[data-testid="stPopover"] button {
        border-radius: 999px;
    }
    </style>
    """
)

if "pipeline" not in st.session_state:
    st.session_state["pipeline"] = ResearchPilotPipeline()
if "paper_cards" not in st.session_state:
    st.session_state["paper_cards"] = load_paper_cards_cache()
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
venue_plan: dict | None = st.session_state["venue_plan"]
venue_collection: dict | None = st.session_state["venue_collection"]

def _arxiv_selection_key(paper: dict, rank: int) -> str:
    base_id = str(paper.get("arxiv_id") or paper.get("entry_id") or f"rank_{rank}")
    normalized = "".join(ch if ch.isalnum() else "_" for ch in base_id)
    normalized = normalized.strip("_") or f"rank_{rank}"
    return f"arxiv_select_{normalized[:100]}_{rank}"


def _split_lines(text: str) -> list[str]:
    return [line.strip() for line in str(text).splitlines() if line.strip()]


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
            parsed = json.loads(raw[start : end + 1])
            return parsed if isinstance(parsed, dict) else {}
    return {}


def _safe_widget_key(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", str(value or "item"))[:120]


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
        title_col, action_col = st.columns([0.78, 0.22], vertical_alignment="top")
        with title_col:
            st.markdown(f"### {title}")
            if chips:
                st.caption(" · ".join(chips))
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
                st.markdown(f"**{FIELD_LABELS_ZH.get(field, field)}**  `/{field}`")
                st.caption(f"中文: {_card_preview(zh_text, 120)}")
                st.write(_card_preview(en_text, 220))
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


tab_search, tab_discovery, tab_watchlist, tab_upload, tab_ask, tab_cards, tab_review, tab_ideas, tab_workspace_chat, tab_library = st.tabs(
    [
        "Search Papers",
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

with tab_search:
    search_topic_input = st.text_input(
        "Research topic",
        value=arxiv_topic,
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
                arxiv_results = ranked_results
                if ranked_results:
                    st.success(f"Found {len(ranked_results)} arXiv papers.")
                else:
                    st.info("No arXiv papers found for this topic.")
            except Exception as exc:
                st.error(f"Search failed: {exc}")

    if arxiv_results:
        st.caption(f'Latest topic: "{st.session_state.get("arxiv_topic", "")}"')
        st.subheader("Search Results")

        for rank, paper in enumerate(arxiv_results, start=1):
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
            for rank, paper in enumerate(arxiv_results, start=1):
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

with tab_discovery:
    st.subheader("Topic-based Conference / Journal Discovery")
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
        include_journals = st.checkbox("Include journals", value=True, key="venue_include_journals")
        include_openreview = st.checkbox("OpenReview", value=True, key="venue_include_openreview")
    with col_b:
        include_openalex = st.checkbox("OpenAlex", value=True, key="venue_include_openalex")
        include_broad_openalex = st.checkbox("Keep broad OpenAlex hits", value=True, key="venue_include_broad_openalex")
    with col_c:
        include_semantic_scholar = st.checkbox("Semantic Scholar", value=True, key="venue_include_semantic_scholar")
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
                with st.spinner("Collecting papers from venue sources and academic search APIs..."):
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
                        st.markdown(f"- [{item.get('label', 'Scholar')}]({item.get('url', '')})")

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

with tab_watchlist:
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
                    "notes": watch_notes,
                }
            )
            st.session_state["watchlist"] = updated_watchlist
            watchlist = updated_watchlist
            st.success(f"Added watch item: {watch_name.strip()}")
        except Exception as exc:
            st.error(f"Failed to add watch item: {exc}")

    st.divider()
    st.subheader("Current Watchlist")
    if not watchlist:
        st.info("暂无关注对象。")
    else:
        for idx, item in enumerate(watchlist):
            item_name = str(item.get("name", ""))
            item_type = str(item.get("type", ""))
            with st.expander(f"{idx + 1}. {item_name} ({item_type})"):
                st.markdown(f"**name**: {item_name}")
                st.markdown(f"**type**: {item_type}")
                st.markdown(f"**authors**: {item.get('authors', [])}")
                st.markdown(f"**institutions**: {item.get('institutions', [])}")
                st.markdown(f"**keywords**: {item.get('keywords', [])}")
                st.markdown(f"**notes**: {item.get('notes', '')}")
                if st.button(
                    "Delete",
                    key=f"watchlist_delete_{idx}_{item_name}",
                    width="content",
                ):
                    try:
                        updated_watchlist = delete_watch_item(idx)
                        st.session_state["watchlist"] = updated_watchlist
                        st.success(f"Deleted watch item: {item_name}")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to delete watch item: {exc}")

    st.divider()
    st.subheader("Watchlist Trend Summary")
    if not st.session_state.get("arxiv_results"):
        st.info("请先去 Search Papers 搜索。")
    else:
        if st.button(
            "Summarize Watchlist Trends",
            width="stretch",
            key="summarize_watchlist_trends_button",
        ):
            try:
                summary = summarize_watchlist_trends(
                    papers=st.session_state["arxiv_results"],
                    watchlist=st.session_state.get("watchlist", []),
                    topic=st.session_state.get("arxiv_topic"),
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
    papers = pipeline.list_papers()
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
    st.caption("Paper card cache file: ./data/outputs/paper_cards_cache.json")
    papers = pipeline.list_papers()
    cached_paper_ids = sorted(paper_cards)
    selectable_papers = sorted(set(papers).union(cached_paper_ids))
    if cached_paper_ids:
        st.caption(f"Loaded cached paper cards: {len(cached_paper_ids)}")
    if not selectable_papers:
        st.info("No papers ingested and no cached paper cards found yet.")
    else:
        selected_paper_id = st.selectbox(
            "Select paper_id",
            options=selectable_papers,
            key="paper_card_selected_paper",
        )
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
        comparison_df = build_comparison_table(paper_cards)
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
    st.subheader("Workspace Chat")
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
    papers = pipeline.list_papers()
    if not papers:
        st.write("No papers ingested yet.")
    else:
        st.write(f"Ingested papers: {len(papers)}")
        for paper_id in papers:
            has_card = paper_id in paper_cards
            card_status = "paper_card_ready" if has_card else "paper_card_not_generated"
            st.write(f"- {paper_id} ({card_status})")
    st.divider()
    st.subheader("Cached Paper Cards")
    if paper_cards:
        st.write(f"Cached paper cards: {len(paper_cards)}")
        st.dataframe(
            [
                {
                    "paper_id": paper_id,
                    "title": card.get("title", "") if isinstance(card, dict) else "",
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
