# Agent-Native Mode

Use this mode when the user wants OpenCode to use its own model subscription instead of ResearchPilot `.env` credentials for LLM-heavy steps.

This does not remove the backend API path. If the user asks for the project backend fallback, or `.env` is configured and autonomous batch generation is preferred, use the original tools such as `researchpilot_paper_card`, `researchpilot_literature_review`, `researchpilot_verify_review`, and `researchpilot_research_ideas`.

OpenCode custom tools cannot call the model directly; they expose deterministic functions that the model can call. Use this two-step pattern:

1. Call a `researchpilot_prepare_*` tool to gather evidence, cached cards, schemas, and instructions.
2. Generate the requested JSON or Markdown with the current OpenCode model, then call a `researchpilot_save_*` tool to validate and persist it.

## Paper Cards

1. Call `researchpilot_prepare_paper_card` with `paper_id`.
2. Generate strict JSON fields: `paper_id`, `title`, `problem`, `method`, `contribution`, `dataset`, `result`, `limitation`, `future_work`, `relevance`.
3. Call `researchpilot_save_paper_card` with the generated object.
4. Repeat per paper.
5. Call `researchpilot_comparison_table`; it is deterministic once cards are cached.

## Literature Reviews

1. Call `researchpilot_prepare_literature_review` with `topic` and optional `paper_ids`.
2. Write the Chinese Markdown review using only supplied cards.
3. Call `researchpilot_save_artifact` with `artifact_type: "literature_review"`.

## CCF Venue Collection Reports

1. Call `researchpilot_collect_venue_papers` after optional `researchpilot_plan_venue_collection`.
2. Call `researchpilot_prepare_venue_paper_summary`.
3. Write the Chinese Markdown collection report using only returned metadata, abstracts, source URLs, and `scholar_followup_urls`.
4. Call `researchpilot_save_artifact` with `artifact_type: "venue_paper_summary"`.

Keep actual `venue` separate from searched `target_venue`; `collection_scope: "broad_openalex"` is a related broad-search hit, not a confirmed publication in that CCF venue.

## Claim Verification

1. Call `researchpilot_prepare_review_verification` with `review_text` or `review_path`.
2. Judge each claim using only the returned evidence.
3. Output statuses only from `supported`, `weakly_supported`, `unsupported`.
4. Call `researchpilot_save_claim_verification`.

## Research Ideas

1. Call `researchpilot_prepare_research_ideas`.
2. Generate Markdown ideas grounded in cards, reviews, and verification signals.
3. Call `researchpilot_save_artifact` with `artifact_type: "research_ideas"`.

## Guardrails

- Use only evidence or cards returned by `prepare_*` tools.
- Never invent missing paper details.
- Prefer empty strings or conservative caveats over speculation.
- Avoid backend-LLM tools when the task asks to use the OpenCode subscription. They remain valid as fallback when `.env` credentials are configured or explicitly requested.
