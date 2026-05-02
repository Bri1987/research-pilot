from pathlib import Path
import sys

import streamlit as st

# Allow `streamlit run app/streamlit_app.py` from repo root without extra PYTHONPATH.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from researchpilot.cards.comparison_table import build_comparison_table
from researchpilot.ingest.pipeline import ResearchPilotPipeline


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

pipeline: ResearchPilotPipeline = st.session_state["pipeline"]
paper_cards: dict[str, dict] = st.session_state["paper_cards"]
literature_review: str = st.session_state["literature_review"]

tab_upload, tab_ask, tab_cards, tab_review, tab_library = st.tabs(
    [
        "Upload PDFs",
        "Ask Papers",
        "Paper Cards",
        "Literature Review",
        "Current Library",
    ]
)

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
                    literature_review = generated_review
                    st.success("Literature review generated.")
                except Exception as exc:
                    st.error(f"Literature review generation failed: {exc}")

        if literature_review:
            st.subheader("Literature Review")
            st.markdown(literature_review)
            st.download_button(
                "Download Markdown",
                data=literature_review,
                file_name="literature_review.md",
                mime="text/markdown",
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
