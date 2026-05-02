from pathlib import Path
import json
import sys

# Allow direct script execution without setting PYTHONPATH manually.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from researchpilot.ingest.pipeline import ResearchPilotPipeline


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "Usage: python scripts/smoke_paper_card.py path/to/file.pdf",
            file=sys.stderr,
        )
        return 1

    pdf_path = argv[1]
    paper_id = Path(pdf_path).stem

    try:
        pipeline = ResearchPilotPipeline()
        pipeline.ingest_pdf(pdf_path, paper_id=paper_id)
        card = pipeline.build_paper_card(paper_id)
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
