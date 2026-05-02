from pathlib import Path
import sys

# Allow direct script execution without setting PYTHONPATH manually.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from researchpilot.ingest.pipeline import ResearchPilotPipeline


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(
            'Usage: python scripts/smoke_rag_qa.py path/to/file.pdf "你的问题"',
            file=sys.stderr,
        )
        return 1

    pdf_path = argv[1]
    question = " ".join(argv[2:]).strip()

    if not question:
        print("Error: question is empty", file=sys.stderr)
        return 1

    try:
        pipeline = ResearchPilotPipeline()
        chunks = pipeline.ingest_pdf(pdf_path, paper_id=Path(pdf_path).stem)
        result = pipeline.ask(question, top_k=8)

        print(f"ingested chunks: {len(chunks)}")
        print("\nanswer:")
        print(result.get("answer", ""))

        evidence = result.get("evidence", [])
        print("\nevidence:")
        if not evidence:
            print("No evidence.")
            return 0

        for item in evidence:
            preview = (item.get("text", "") or "").strip()[:200]
            rank = item.get("rank", "")
            score = float(item.get("score", 0.0))
            paper_id = item.get("paper_id", "")
            page = item.get("page", "")
            print(
                f"rank={rank} score={score:.4f} "
                f"paper_id={paper_id} page={page} "
                f"text_preview={preview}"
            )

        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
