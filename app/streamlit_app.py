from pathlib import Path
import sys

import streamlit as st

# Allow `streamlit run app/streamlit_app.py` from repo root without extra PYTHONPATH.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from researchpilot.cards.comparison_table import build_comparison_table
from researchpilot.ingest.pipeline import ResearchPilotPipeline
from researchpilot.review.review_diff import make_unified_diff
from researchpilot.search.arxiv_search import download_arxiv_paper
from researchpilot.search.arxiv_search import search_arxiv_papers


UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="ResearchPilot",
    layout="wide",
)
st.title("ResearchPilot: Citation-Grounded AI Research Assistant")

if "pipeline" not in st.session_state:
    st.session_state["pipeline"] = ResearchPilotPipeline()
if "paper_cards" not in st.session_state:
    st.session_state["paper_cards"] = {}
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

pipeline: ResearchPilotPipeline = st.session_state["pipeline"]
paper_cards: dict[str, dict] = st.session_state["paper_cards"]
literature_review: str = st.session_state["literature_review"]
claim_verification: list[dict] = st.session_state["claim_verification"]
revised_literature_review: str = st.session_state["revised_literature_review"]
review_versions: list[dict] = st.session_state["review_versions"]
active_review_version: int = st.session_state["active_review_version"]
arxiv_results: list[dict] = st.session_state["arxiv_results"]
arxiv_topic: str = st.session_state["arxiv_topic"]

def _arxiv_selection_key(paper: dict, rank: int) -> str:
    base_id = str(paper.get("arxiv_id") or paper.get("entry_id") or f"rank_{rank}")
    normalized = "".join(ch if ch.isalnum() else "_" for ch in base_id)
    normalized = normalized.strip("_") or f"rank_{rank}"
    return f"arxiv_select_{normalized[:100]}_{rank}"


tab_search, tab_upload, tab_ask, tab_cards, tab_review, tab_library = st.tabs(
    [
        "Search Papers",
        "Upload PDFs",
        "Ask Papers",
        "Paper Cards",
        "Literature Review",
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
                st.session_state["arxiv_results"] = results
                st.session_state["arxiv_topic"] = topic
                arxiv_results = results
                if results:
                    st.success(f"Found {len(results)} arXiv papers.")
                else:
                    st.info("No arXiv papers found for this topic.")
            except Exception as exc:
                st.error(f"Search failed: {exc}")

    if arxiv_results:
        st.caption(f'Latest topic: "{st.session_state.get("arxiv_topic", "")}"')
        st.subheader("Search Results")

        for rank, paper in enumerate(arxiv_results, start=1):
            paper_title = str(paper.get("title", ""))
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

with tab_upload:
    st.caption(f"Uploaded files are saved to: {UPLOAD_DIR}")
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
    papers = pipeline.list_papers()
    if not papers:
        st.info("No papers ingested yet. Please upload and ingest PDFs first.")
    else:
        selected_paper_id = st.selectbox(
            "Select paper_id",
            options=papers,
            key="paper_card_selected_paper",
        )
        if st.button("Generate Paper Card", width="stretch"):
            try:
                card = pipeline.build_paper_card(selected_paper_id)
                paper_cards[selected_paper_id] = card
                st.success(f"Paper card generated for: {selected_paper_id}")
            except Exception as exc:
                st.error(f"Paper card generation failed: {exc}")

        current_card = paper_cards.get(selected_paper_id)
        if current_card is None:
            st.info("No paper card generated for this paper yet.")
        else:
            if isinstance(current_card, dict):
                st.subheader("Paper Card (JSON)")
                st.json(current_card)

                if "raw" in current_card or "parse_error" in current_card:
                    warning_msg = (
                        f"raw={current_card.get('raw', '')}\n\n"
                        f"parse_error={current_card.get('parse_error', '')}"
                    )
                    st.warning(warning_msg)

                st.subheader("Paper Card (Readable)")
                st.markdown(f"**title**: {current_card.get('title', '')}")
                st.markdown(f"**problem**: {current_card.get('problem', '')}")
                st.markdown(f"**method**: {current_card.get('method', '')}")
                st.markdown(
                    f"**contribution**: {current_card.get('contribution', '')}"
                )
                st.markdown(f"**dataset**: {current_card.get('dataset', '')}")
                st.markdown(f"**result**: {current_card.get('result', '')}")
                st.markdown(f"**limitation**: {current_card.get('limitation', '')}")
                st.markdown(f"**future_work**: {current_card.get('future_work', '')}")
                st.markdown(f"**relevance**: {current_card.get('relevance', '')}")
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
                value=4,
            )
            if st.button("Verify Claims", width="stretch"):
                try:
                    with st.spinner("Verifying claims..."):
                        results = pipeline.verify_literature_review(
                            current_text,
                            top_k=verify_top_k,
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
