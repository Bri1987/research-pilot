# Agent-Native Mode

Use this mode when the user wants Codex to use its own model subscription instead of ResearchPilot `.env` credentials for LLM-heavy steps.

This does not remove the backend API path. If the user asks for the project backend fallback, or `.env` is configured and autonomous batch generation is preferred, use the original commands such as `paper_card`, `literature_review`, `verify_review`, and `research_ideas`.

The pattern is two-step:

1. Run a deterministic `prepare_*` command to gather evidence, cached cards, schemas, and task instructions.
2. Use the current Codex model to generate the requested JSON or Markdown, then run a deterministic `save_*` command to validate and persist it.

## Paper Cards

```bash
python -m researchpilot.agent_cli prepare_paper_card '{"paper_id":"..."}'
```

Generate one strict JSON object with these fields:

```json
{
  "paper_id": "...",
  "title": "...",
  "problem": "...",
  "method": "...",
  "contribution": "...",
  "dataset": "...",
  "result": "...",
  "limitation": "...",
  "future_work": "...",
  "relevance": "..."
}
```

Then save:

```bash
python -m researchpilot.agent_cli save_paper_card '{"card":{...}}'
```

Repeat for each paper. Once cards are cached, comparison tables are deterministic:

```bash
python -m researchpilot.agent_cli comparison_table '{"paper_ids":["..."],"save_csv":true}'
```

## Literature Reviews

```bash
python -m researchpilot.agent_cli prepare_literature_review '{"topic":"...","paper_ids":["..."]}'
```

Write the review using the current Codex model, then persist:

```bash
python -m researchpilot.agent_cli save_artifact '{"artifact_type":"literature_review","text":"..."}'
```

## CCF Venue Collection Reports

```bash
python -m researchpilot.agent_cli collect_venue_papers '{"topic":"...","years":[2026,2025,2024]}'
python -m researchpilot.agent_cli prepare_venue_paper_summary '{"max_papers":30}'
```

Write the venue/journal paper collection report using only the returned metadata, abstracts, source URLs, and `scholar_followup_urls`. Save with:

```bash
python -m researchpilot.agent_cli save_artifact '{"artifact_type":"venue_paper_summary","text":"..."}'
```

Preserve the distinction between actual `venue` and searched `target_venue`; treat `collection_scope:"broad_openalex"` as a related broad-search hit, not a confirmed CCF venue publication.

## Claim Verification

```bash
python -m researchpilot.agent_cli prepare_review_verification '{"review_path":"data/outputs/agent/latest_literature_review.md","top_k":5}'
```

For each returned claim, judge using only the provided evidence. Output a JSON list where each item has:

```json
{
  "claim": "...",
  "status": "supported | weakly_supported | unsupported",
  "reason": "...",
  "best_evidence": ["E1"],
  "evidence": [],
  "suggested_rewrite": "..."
}
```

Then save:

```bash
python -m researchpilot.agent_cli save_claim_verification '{"results":[...]}'
```

## Research Ideas

```bash
python -m researchpilot.agent_cli prepare_research_ideas '{"topic":"...","paper_ids":["..."],"verification_path":"data/outputs/agent/latest_claim_verification.json"}'
```

Generate Markdown ideas with Motivation, Research Gap, Proposed Method, Why It May Be Novel, Required Evidence or Experiments, Risks, and Related Existing Work. Save with:

```bash
python -m researchpilot.agent_cli save_artifact '{"artifact_type":"research_ideas","text":"..."}'
```

## Guardrails

- Use only evidence or cards returned by `prepare_*` commands.
- Never use unstated paper details to fill missing card fields.
- Prefer empty strings or conservative caveats over speculation.
- Do not call backend-LLM commands such as `paper_card`, `literature_review`, `verify_review`, or `research_ideas` when the task explicitly asks to use the agent framework subscription. They remain valid as fallback when `.env` credentials are configured or explicitly requested.
