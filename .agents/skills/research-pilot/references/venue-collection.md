# Venue Collection

Use this workflow when the user asks for research-direction paper collection across CCF conferences/journals and broader academic sources. By default `researchpilot_collect_venue_papers` includes arXiv, OpenReview, OpenAlex, and optional Semantic Scholar. Set `include_arxiv:false` only when the user explicitly wants to exclude arXiv.

1. Call `researchpilot_plan_venue_collection` with `topic`.
2. Call `researchpilot_collect_venue_papers` with optional `years`, `domains`, `venues`, `max_results_per_venue`, `max_total`, `include_arxiv`, and `include_semantic_scholar`.
3. For OpenCode subscription generation, call `researchpilot_prepare_venue_paper_summary`, write the Markdown report yourself, then call `researchpilot_save_artifact` with `artifact_type: "venue_paper_summary"`.
4. Use `researchpilot_metadata_paper_cards` for quick candidate cards from collection metadata when full PDFs are not yet downloaded.
5. If `.env` is configured and backend fallback is desired, call `researchpilot_venue_paper_summary`.

Selection rules:
- AI topics should consider NeurIPS, ICML, ICLR, AAAI, ACL, CVPR/ICCV, KDD, JMLR, TPAMI when relevant.
- Formal verification / PL / software topics should consider CAV, LICS, POPL, PLDI, OOPSLA, FM, TACAS, FMCAD, ICSE, FSE, ASE, ISSTA, TOPLAS, TSE, TOSEM when relevant.
- Cross-field topics should keep both sides, e.g. AI venues plus CAV/POPL/PLDI for formal verification + AI.
- Use `venues` to force include acronyms and `domains` to disambiguate.
- Keep `include_arxiv:true` for default discovery; use the separate `researchpilot_search_arxiv` tool only when the user asks to look only at arXiv.
- Set `include_broad_openalex:false` when the user wants only papers actually published in selected venues.

Source semantics:
- `target_venue` is the searched CCF venue; `venue` is the actual reported source.
- `collection_scope:"venue"` means a selected-venue paper.
- `collection_scope:"arxiv"` means arXiv found a related topic-search paper.
- `collection_scope:"broad_openalex"` means a related OpenAlex hit; do not present it as published in the target venue.
- `collection_scope:"broad_semantic_scholar"` means a related Semantic Scholar topic-search hit; manually confirm venue/source before making publication-venue claims.
- `scholar_followup_urls` are manual Google Scholar links; the tool does not scrape Google Scholar.
