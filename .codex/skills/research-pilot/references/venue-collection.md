# Venue Collection

Use this workflow when the user asks for research-direction paper collection beyond arXiv, especially when they mention CCF conferences/journals, OpenReview, official conference pages, journals, or Google Scholar follow-up.

## Workflow

1. Plan venues:

```bash
python -m researchpilot.agent_cli plan_venue_collection '{"topic":"形式化验证与大模型结合","max_venues":12}'
```

2. Collect recent papers:

```bash
python -m researchpilot.agent_cli collect_venue_papers '{"topic":"形式化验证与大模型结合","years":[2026,2025,2024],"max_results_per_venue":12,"max_total":60,"include_semantic_scholar":true}'
```

3. Agent-native summary:

```bash
python -m researchpilot.agent_cli prepare_venue_paper_summary '{"max_papers":30}'
```

Write the Chinese Markdown report with the current Codex model, then persist it:

```bash
python -m researchpilot.agent_cli save_artifact '{"artifact_type":"venue_paper_summary","text":"..."}'
```

Generate metadata-level paper cards from the same collection when the user wants candidate cards before PDF ingestion:

```bash
python -m researchpilot.agent_cli metadata_paper_cards '{"max_cards":10}'
```

If `.env` is configured and the user wants backend fallback, use `venue_paper_summary` directly.

## Selection Rules

- For single-domain AI topics, expect venues such as NeurIPS, ICML, ICLR, AAAI, ACL, CVPR/ICCV, KDD, JMLR, TPAMI depending on keywords.
- For formal verification, PL, or software topics, expect venues such as CAV, LICS, POPL, PLDI, OOPSLA, FM, TACAS, FMCAD, ICSE, FSE, ASE, ISSTA, TOPLAS, TSE, TOSEM.
- For cross-field topics, keep both sides. Example: formal verification + AI should include ML venues and formal-methods/PL venues.
- Use `venues` to force include acronyms when the user names specific venues.
- Use `domains` when topic wording is ambiguous, e.g. `["ai","formal_methods"]`.
- Set `include_broad_openalex:false` when the user wants only papers actually published in the selected venues.

## Source Semantics

- `target_venue` is the venue ResearchPilot searched because it matched the topic/CCF plan.
- `venue` is the actual source reported by OpenReview/OpenAlex.
- `collection_scope:"venue"` means the paper is from the selected venue.
- `collection_scope:"broad_openalex"` means OpenAlex found a related paper during venue-targeted search; do not present it as published in the target venue.
- `collection_scope:"broad_semantic_scholar"` means Semantic Scholar found a related topic-search paper; manually confirm venue/source before making publication-venue claims.
- `scholar_followup_urls` are generated links for manual Google Scholar checks. The tool does not scrape Google Scholar.

## CCF Caveat

The local CCF seed is compact and meant for planning. Treat `ccf_rank` as a rank hint and verify the official CCF directory for high-stakes decisions.
