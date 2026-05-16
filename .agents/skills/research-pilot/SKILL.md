---
name: research-pilot
description: Use ResearchPilot to run local scientific-literature workflows: arXiv and CCF conference/journal discovery, PDF or text ingestion, evidence retrieval, citation-grounded QA, paper cards, comparison tables, literature reviews, claim-level citation verification, conservative rewrites, research ideas, and watchlist ranking.
compatibility: opencode
metadata:
  project: ResearchPilot
  tool_prefix: researchpilot
---

# ResearchPilot

Use this skill when the task is about scientific paper discovery, local-paper RAG, literature review generation, citation verification, review revision, research idea generation, or watchlist-based paper triage in this project.

## Workflow

1. Call `researchpilot_status` first to inspect local corpus state, cached paper cards, watchlist state, and LLM configuration.
2. Get papers into the local corpus:
   - Use `researchpilot_search_arxiv`, then `researchpilot_download_arxiv_result`, then `researchpilot_ingest_pdf`.
   - For CCF conference/journal discovery, use `researchpilot_plan_venue_collection`, then `researchpilot_collect_venue_papers` (OpenReview/OpenAlex plus optional Semantic Scholar), then `researchpilot_prepare_venue_paper_summary` and `researchpilot_save_artifact`; optionally download/ingest selected PDFs afterward.
   - Or use `researchpilot_ingest_pdf` for existing PDFs.
   - Or use `researchpilot_ingest_text` for quick tool tests and non-PDF excerpts.
3. Use `researchpilot_retrieve` for evidence inspection. Default `retrieval_mode` is `bm25`; use `hybrid` only when `sentence-transformers` and its embedding model are installed or cached.
4. For LLM-heavy outputs, choose one of two supported modes:
   - Agent-native mode: if the user wants to use the OpenCode subscription or `.env` is absent, read `references/agent-native-mode.md` and use the `researchpilot_prepare_*` / `researchpilot_save_*` tools.
   - Backend API fallback: if `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` are configured, or the user explicitly asks for the project backend to run autonomously, use the original LLM-backed tools directly:
   - `researchpilot_ask`
   - `researchpilot_paper_card`
   - `researchpilot_build_paper_cards`
   - `researchpilot_literature_review`
   - `researchpilot_verify_review`
   - `researchpilot_rewrite_review`
   - `researchpilot_research_ideas`
   - `researchpilot_watchlist` with `summarize_last_search`
5. For a full review loop, run:
   `build_paper_cards` -> `comparison_table` -> `literature_review` -> `verify_review` -> `rewrite_review` -> `research_ideas`.

For non-arXiv CCF venue collection details, read `references/venue-collection.md`.
Use `researchpilot_metadata_paper_cards` when the user wants quick candidate paper cards from a collected venue/Semantic Scholar result set before downloading full PDFs.

## State and Artifacts

- Persisted chunks live in `data/agent_state/chunks.json`.
- Latest arXiv results live in `data/agent_state/last_arxiv_results.json`.
- Latest CCF venue collection lives in `data/agent_state/last_venue_collection.json`.
- Paper card cache uses the existing `data/outputs/paper_cards_cache.json`.
- Generated agent artifacts are written under `data/outputs/agent/`.

## LLM Setup

The backend API fallback remains supported. The project Python backend uses OpenAI-compatible chat completions through `.env`:

```env
OPENAI_API_KEY=<your key>
OPENAI_BASE_URL=https://opencode.ai/zen/v1
OPENAI_MODEL=minimax-m2.5-free
```

In OpenCode itself, this project config points the agent to `opencode/minimax-m2.5-free`. Connect it with `/connect` -> `OpenCode Zen`, then confirm the exact available model with `/models`.

When `.env` is intentionally absent, use `references/agent-native-mode.md`; OpenCode tools prepare evidence and save outputs, while the current OpenCode model generates the paper-card JSON or Markdown.

## Guardrails

- Never claim a generated review is fully verified until `researchpilot_verify_review` has been run.
- Treat `weakly_supported` and `unsupported` claims as revision targets.
- Keep paper IDs stable. Re-ingesting the same `paper_id` replaces its chunks and invalidates the cached paper card.
- Prefer saved artifact paths for long reviews and verification JSON rather than pasting large text into later calls.
- In venue collection results, actual `venue` and searched `target_venue` can differ; `collection_scope: "broad_openalex"` is a related OpenAlex hit, not a confirmed publication in that CCF venue; `collection_scope: "broad_semantic_scholar"` is a Semantic Scholar topic hit that needs manual venue confirmation.
