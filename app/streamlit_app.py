from pathlib import Path
import sys

import streamlit as st

# Allow `streamlit run app/streamlit_app.py` from repo root without extra PYTHONPATH.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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

pipeline: ResearchPilotPipeline = st.session_state["pipeline"]

tab_upload, tab_ask, tab_library = st.tabs(
    ["Upload PDFs", "Ask Papers", "Current Library"]
)

with tab_upload:
    st.caption(f"Uploaded files are saved to: {UPLOAD_DIR}")
    uploaded_files = st.file_uploader(
        "Select one or more PDF files",
        type=["pdf"],
        accept_multiple_files=True,
    )

    if st.button("Ingest PDFs", use_container_width=True):
        if not uploaded_files:
            st.warning("Please upload at least one PDF file first.")
        else:
            for uploaded_file in uploaded_files:
                try:
                    target_path = UPLOAD_DIR / uploaded_file.name
                    target_path.write_bytes(uploaded_file.getbuffer())
                    chunks = pipeline.ingest_pdf(str(target_path))
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

    if st.button("Ask", use_container_width=True):
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

with tab_library:
    papers = pipeline.list_papers()
    if not papers:
        st.write("No papers ingested yet.")
    else:
        st.write(f"Ingested papers: {len(papers)}")
        for paper_id in papers:
            st.write(f"- {paper_id}")
