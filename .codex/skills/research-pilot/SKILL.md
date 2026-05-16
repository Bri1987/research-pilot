---
name: "research-pilot"
description: "Use ResearchPilot for scientific paper discovery including arXiv and CCF conference/journal venue collection, local PDF or text ingestion, evidence retrieval, citation-grounded QA, paper cards, comparison tables, literature reviews, claim-level citation verification, conservative rewrites, research ideas, and watchlist ranking."
metadata:
  project: "ResearchPilot"
  local_adapter: "researchpilot.agent_cli"
---

# ResearchPilot

Use this skill when working in the ResearchPilot project on scientific paper search, local-paper RAG, literature review generation, claim verification, review revision, research ideas, or watchlist triage.

## Locate the project

The project root contains `researchpilot/agent_cli.py`.

If the current directory is the parent workspace, use `research-pilot/` as the project root. Otherwise, search upward or ask for the ResearchPilot path before running commands.

## Local adapter

Use the Python adapter instead of the Streamlit app for agent workflows:

```bash
python -m researchpilot.agent_cli status
python -m researchpilot.agent_cli <command> '<json-args>'
```

If dependencies are installed in `.venv`, prefer:

```bash
.venv/bin/python -m researchpilot.agent_cli status
```

Set `PYTHONPATH` to the project root only if importing `researchpilot` fails.

## Workflow

1. Run `status` first to inspect corpus state, paper-card cache, watchlist state, and LLM environment.
2. Add papers:
   - arXiv path: `search_arxiv` -> `download_arxiv_result` -> `ingest_pdf`.
   - CCF venue path: `plan_venue_collection` -> `collect_venue_papers` (OpenReview/OpenAlex plus optional Semantic Scholar) -> `prepare_venue_paper_summary` -> `save_artifact`; optionally download/ingest selected PDFs afterward.
   - Existing PDF path: `ingest_pdf`.
   - Quick test path: `ingest_text`.
3. Inspect evidence with `retrieve` before making synthesis claims.
4. For LLM-heavy outputs, choose one of two supported modes:
   - Agent-native mode: if the user wants to use the Codex subscription or `.env` is absent, read `references/agent-native-mode.md` and use the `prepare_*` / `save_*` commands.
   - Backend API fallback: if `.env` has `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL`, or the user explicitly asks for the project backend to run autonomously, use the original LLM-backed commands directly.
5. Full review loop:
   `build_paper_cards` -> `comparison_table` -> `literature_review` -> `verify_review` -> `rewrite_review` -> `research_ideas`.

For non-arXiv conference/journal discovery, especially CCF venue selection, OpenReview/OpenAlex collection, cross-field topics, or Google Scholar follow-up URLs, read `references/venue-collection.md`.

## Commands

- `status`: show project state and LLM configuration.
- `search_arxiv`: search arXiv and save latest results.
- `plan_venue_collection`: infer domains and CCF conference/journal venues for a topic.
- `collect_venue_papers`: collect recent papers from OpenReview/OpenAlex and optional Semantic Scholar for selected venues/topic and save the latest collection.
- `download_arxiv_result`: download a saved arXiv result by 1-based rank.
- `download_pdf`: download a direct PDF URL.
- `ingest_pdf`: parse and chunk a local PDF into `data/agent_state/chunks.json`.
- `ingest_text`: persist raw text as a paper for tests or snippets.
- `list_papers`: list ingested papers.
- `retrieve`: retrieve evidence chunks. Default `retrieval_mode` is `bm25`.
- `ask`: answer from evidence using citation-grounded LLM generation.
- `paper_card` / `build_paper_cards`: generate structured paper cards.
- `prepare_paper_card` / `save_paper_card`: agent-native paper cards without `.env` LLM credentials.
- `comparison_table`: build a CSV/JSON comparison from paper cards.
- `prepare_venue_paper_summary` / `venue_paper_summary`: agent-native or backend-LLM summary of a saved CCF venue/journal collection.
- `metadata_paper_cards`: create conservative bilingual metadata-level paper cards from a saved venue/Semantic Scholar collection without downloading PDFs.
- `literature_review`: generate a Chinese Markdown review from paper cards.
- `prepare_literature_review` / `save_artifact`: agent-native review writing without `.env` LLM credentials.
- `verify_review`: run claim-level citation verification.
- `prepare_review_verification` / `save_claim_verification`: agent-native claim verification without `.env` LLM credentials.
- `rewrite_review`: generate a conservative revised review.
- `research_ideas`: generate candidate future research ideas.
- `prepare_research_ideas`: agent-native research idea generation without `.env` LLM credentials.
- `watchlist`: list/add/delete/rank/summarize watchlist items.

## Examples

```bash
python -m researchpilot.agent_cli ingest_text '{"paper_id":"demo","text":"Claim verification checks whether retrieved evidence supports a claim."}'
python -m researchpilot.agent_cli retrieve '{"query":"claim verification evidence","top_k":3}'
python -m researchpilot.agent_cli literature_review '{"topic":"program alignment","build_missing_cards":true}'
```

## State and artifacts

- Persisted chunks: `data/agent_state/chunks.json`
- Latest arXiv results: `data/agent_state/last_arxiv_results.json`
- Latest venue collection: `data/agent_state/last_venue_collection.json`
- Paper-card cache: `data/outputs/paper_cards_cache.json`
- Generated artifacts: `data/outputs/agent/`

## LLM setup

The backend API fallback remains supported. It uses OpenAI-compatible chat completions from `.env`. For OpenCode Zen MiniMax M2.5 Free:

```env
OPENAI_API_KEY=<your key>
OPENAI_BASE_URL=https://opencode.ai/zen/v1
OPENAI_MODEL=minimax-m2.5-free
```

When `.env` is intentionally absent, use `references/agent-native-mode.md` and let Codex produce the JSON/Markdown between deterministic prepare/save commands.

## Guardrails

- Do not claim a generated review is verified until `verify_review` has run.
- Treat `weakly_supported` and `unsupported` claims as revision targets.
- Keep `paper_id` stable. Re-ingesting a paper replaces chunks for that `paper_id`.
- Pass saved artifact paths between long-running commands instead of pasting large review or verification payloads.
- Prefer `retrieval_mode: "bm25"` unless `sentence-transformers` and the embedding model are confirmed available.
- In venue collection results, distinguish actual `venue` from `target_venue`; `collection_scope: "broad_openalex"` means it is a related OpenAlex hit, not necessarily a paper published in that CCF venue; `collection_scope: "broad_semantic_scholar"` means it is a Semantic Scholar topic hit and needs manual venue confirmation.
