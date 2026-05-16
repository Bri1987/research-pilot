import { tool } from "@opencode-ai/plugin"
import { spawn } from "child_process"
import { existsSync } from "fs"
import path from "path"

type ToolContext = {
  directory?: string
  worktree?: string
}

type JsonRecord = Record<string, unknown>

function projectRoot(context: ToolContext): string {
  return context.worktree || context.directory || process.cwd()
}

function pythonCandidates(root: string): string[] {
  const envPython = process.env.RESEARCHPILOT_PYTHON
  const candidates = [
    envPython,
    path.join(root, ".venv", "bin", "python"),
    path.join(root, ".venv", "bin", "python3"),
    "python3.12",
    "python3.11",
    "python3.10",
    "python3",
  ]
  return candidates.filter((item): item is string => Boolean(item))
}

function pickPython(root: string): string {
  for (const candidate of pythonCandidates(root)) {
    if (candidate.includes(path.sep) && !existsSync(candidate)) continue
    return candidate
  }
  return "python3"
}

async function runResearchPilot(command: string, args: JsonRecord, context: ToolContext): Promise<string> {
  const root = projectRoot(context)
  const python = pickPython(root)
  const env = {
    ...process.env,
    PYTHONPATH: process.env.PYTHONPATH ? `${root}${path.delimiter}${process.env.PYTHONPATH}` : root,
  }

  return await new Promise((resolve, reject) => {
    const child = spawn(python, ["-m", "researchpilot.agent_cli", "tool", command], {
      cwd: root,
      env,
      stdio: ["pipe", "pipe", "pipe"],
    })

    let stdout = ""
    let stderr = ""
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString()
    })
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString()
    })
    child.on("error", (error) => {
      reject(error)
    })
    child.on("close", (code) => {
      let parsed: unknown
      try {
        parsed = JSON.parse(stdout)
      } catch {
        parsed = null
      }

      if (code !== 0) {
        const details = parsed ? JSON.stringify(parsed, null, 2) : stdout.trim()
        reject(new Error([details, stderr.trim()].filter(Boolean).join("\n")))
        return
      }

      resolve(parsed ? JSON.stringify(parsed, null, 2) : stdout.trim())
    })

    child.stdin.write(JSON.stringify(args))
    child.stdin.end()
  })
}

export const status = tool({
  description: "Inspect ResearchPilot agent-tool state, ingested papers, cached paper cards, watchlist count, and LLM environment setup.",
  args: {},
  async execute(args, context) {
    return await runResearchPilot("status", args, context)
  },
})

export const search_arxiv = tool({
  description: "Search arXiv for papers, optionally rank results against the local watchlist, and save the latest result set for download or ranking.",
  args: {
    query: tool.schema.string().describe("arXiv search query."),
    max_results: tool.schema.number().optional().describe("Maximum results to return, default 5."),
    sort_by: tool.schema.string().optional().describe("Sort criterion: relevance or submitted_date."),
    include_watchlist: tool.schema.boolean().optional().describe("Rank against local watchlist, default true."),
    save_results: tool.schema.boolean().optional().describe("Save as latest arXiv results, default true."),
  },
  async execute(args, context) {
    return await runResearchPilot("search_arxiv", args, context)
  },
})

export const plan_venue_collection = tool({
  description: "Plan CCF-standard conference/journal paper collection for a research topic, including cross-field venue selection and Google Scholar follow-up URLs.",
  args: {
    topic: tool.schema.string().describe("Research topic or field."),
    domains: tool.schema.array(tool.schema.string()).optional().describe("Optional domain hints, e.g. ai, formal_methods, programming_languages."),
    keywords: tool.schema.array(tool.schema.string()).optional().describe("Optional extra search keywords."),
    venues: tool.schema.array(tool.schema.string()).optional().describe("Optional venue acronyms to force include, e.g. ICLR, CAV, PLDI."),
    include_journals: tool.schema.boolean().optional().describe("Include CCF journals as well as conferences, default true."),
    max_venues: tool.schema.number().optional().describe("Maximum venues to return, default 12."),
  },
  async execute(args, context) {
    return await runResearchPilot("plan_venue_collection", args, context)
  },
})

export const collect_venue_papers = tool({
  description: "Collect recent papers for selected CCF conferences/journals using OpenReview, OpenAlex, and optionally Semantic Scholar, with actual source URLs and broad-search follow-up hints.",
  args: {
    topic: tool.schema.string().describe("Research topic or field."),
    domains: tool.schema.array(tool.schema.string()).optional().describe("Optional domain hints, e.g. ai, formal_methods."),
    keywords: tool.schema.array(tool.schema.string()).optional().describe("Optional extra search keywords."),
    venues: tool.schema.array(tool.schema.string()).optional().describe("Optional venue acronyms to force include."),
    years: tool.schema.array(tool.schema.number()).optional().describe("Years to search. Defaults to current and previous two years."),
    include_journals: tool.schema.boolean().optional().describe("Include journals as candidate venues, default true."),
    max_venues: tool.schema.number().optional().describe("Maximum venues to search, default 10."),
    max_results_per_venue: tool.schema.number().optional().describe("Provider results per venue, default 8."),
    max_total: tool.schema.number().optional().describe("Maximum papers returned after dedupe/filtering, default 60."),
    include_openreview: tool.schema.boolean().optional().describe("Query OpenReview venue APIs when available, default true."),
    include_openalex: tool.schema.boolean().optional().describe("Query OpenAlex works API, default true."),
    include_broad_openalex: tool.schema.boolean().optional().describe("Keep OpenAlex broad-search papers not actually published in the target venue, default true."),
    include_semantic_scholar: tool.schema.boolean().optional().describe("Query Semantic Scholar Academic Graph as a broad topic source, default false."),
    include_broad_semantic_scholar: tool.schema.boolean().optional().describe("Keep broad Semantic Scholar topic-search hits, default true."),
    min_relevance_score: tool.schema.number().optional().describe("Minimum relevance score, default 1.0."),
    save: tool.schema.boolean().optional().describe("Save collection artifact and latest pointer, default true."),
  },
  async execute(args, context) {
    return await runResearchPilot("collect_venue_papers", args, context)
  },
})

export const download_pdf = tool({
  description: "Download a PDF from a URL into the project, usually data/uploads, for later ingestion.",
  args: {
    pdf_url: tool.schema.string().describe("Direct PDF URL."),
    filename: tool.schema.string().optional().describe("Optional local filename."),
    output_dir: tool.schema.string().optional().describe("Output directory relative to project root, default data/uploads."),
  },
  async execute(args, context) {
    return await runResearchPilot("download_pdf", args, context)
  },
})

export const download_arxiv_result = tool({
  description: "Download a paper PDF from the latest saved arXiv search results by 1-based rank.",
  args: {
    rank: tool.schema.number().describe("1-based rank in the latest saved arXiv search results."),
    output_dir: tool.schema.string().optional().describe("Output directory relative to project root, default data/uploads."),
  },
  async execute(args, context) {
    return await runResearchPilot("download_arxiv_result", args, context)
  },
})

export const ingest_pdf = tool({
  description: "Parse a local PDF, chunk it, and persist it in the ResearchPilot agent corpus for retrieval and downstream writing tools.",
  args: {
    pdf_path: tool.schema.string().describe("PDF path, absolute or relative to project root."),
    paper_id: tool.schema.string().optional().describe("Stable paper id, default PDF filename stem."),
    title: tool.schema.string().optional().describe("Human-readable title, default paper_id."),
    chunk_size: tool.schema.number().optional().describe("Chunk size in characters, default 1200."),
    overlap: tool.schema.number().optional().describe("Chunk overlap in characters, default 200."),
  },
  async execute(args, context) {
    return await runResearchPilot("ingest_pdf", args, context)
  },
})

export const ingest_text = tool({
  description: "Persist raw text as a ResearchPilot paper. Useful for quick agent tests or non-PDF snippets.",
  args: {
    paper_id: tool.schema.string().describe("Stable paper id."),
    text: tool.schema.string().describe("Paper text or excerpt to chunk and store."),
    title: tool.schema.string().optional().describe("Human-readable title, default paper_id."),
    page: tool.schema.number().optional().describe("Synthetic page number, default 1."),
    chunk_size: tool.schema.number().optional().describe("Chunk size in characters, default 1200."),
    overlap: tool.schema.number().optional().describe("Chunk overlap in characters, default 200."),
  },
  async execute(args, context) {
    return await runResearchPilot("ingest_text", args, context)
  },
})

export const list_papers = tool({
  description: "List papers currently persisted in the ResearchPilot agent corpus.",
  args: {},
  async execute(args, context) {
    return await runResearchPilot("list_papers", args, context)
  },
})

export const retrieve = tool({
  description: "Retrieve evidence chunks from the persisted ResearchPilot corpus using BM25 by default or hybrid retrieval when dependencies are installed.",
  args: {
    query: tool.schema.string().describe("Retrieval query."),
    top_k: tool.schema.number().optional().describe("Number of evidence chunks, default 5."),
    retrieval_mode: tool.schema.string().optional().describe("bm25 or hybrid, default bm25."),
  },
  async execute(args, context) {
    return await runResearchPilot("retrieve", args, context)
  },
})

export const ask = tool({
  description: "Answer a question using retrieved ResearchPilot evidence and citation-grounded LLM generation.",
  args: {
    question: tool.schema.string().describe("Question to answer from the ingested papers."),
    top_k: tool.schema.number().optional().describe("Evidence chunks per answer, default 8."),
    retrieval_mode: tool.schema.string().optional().describe("bm25 or hybrid, default bm25."),
  },
  async execute(args, context) {
    return await runResearchPilot("ask", args, context)
  },
})

export const paper_card = tool({
  description: "Build or read a structured paper card using the ResearchPilot backend LLM. If .env is not configured, use prepare_paper_card then save_paper_card instead.",
  args: {
    paper_id: tool.schema.string().describe("Paper id in the ResearchPilot corpus."),
    refresh: tool.schema.boolean().optional().describe("Regenerate even if cached, default false."),
  },
  async execute(args, context) {
    return await runResearchPilot("paper_card", args, context)
  },
})

export const prepare_paper_card = tool({
  description: "Agent-native mode: gather paper evidence and schema so the current OpenCode model can generate a paper card without project API keys.",
  args: {
    paper_id: tool.schema.string().describe("Paper id in the ResearchPilot corpus."),
    max_chunks: tool.schema.number().optional().describe("Max evidence chunks to return, default 10."),
    text_limit: tool.schema.number().optional().describe("Max characters per chunk, default 1800."),
  },
  async execute(args, context) {
    return await runResearchPilot("prepare_paper_card", args, context)
  },
})

export const save_paper_card = tool({
  description: "Agent-native mode: validate and cache a paper card generated by the current OpenCode model.",
  args: {
    paper_id: tool.schema.string().optional().describe("Paper id. If omitted, uses card.paper_id."),
    card: tool.schema.object({}).passthrough().optional().describe("Paper card JSON object generated by the agent."),
    card_json: tool.schema.string().optional().describe("Paper card JSON object as a string."),
  },
  async execute(args, context) {
    return await runResearchPilot("save_paper_card", args, context)
  },
})

export const build_paper_cards = tool({
  description: "Build structured paper cards using the ResearchPilot backend LLM. If .env is not configured, use prepare_paper_card/save_paper_card per paper.",
  args: {
    paper_ids: tool.schema.array(tool.schema.string()).optional().describe("Paper ids to process. Omit to process all ingested papers."),
    refresh: tool.schema.boolean().optional().describe("Regenerate cached cards, default false."),
  },
  async execute(args, context) {
    return await runResearchPilot("build_paper_cards", args, context)
  },
})

export const comparison_table = tool({
  description: "Deterministically create a multi-paper comparison table from cached paper cards. Does not require project API keys unless build_missing_cards is true.",
  args: {
    paper_ids: tool.schema.array(tool.schema.string()).optional().describe("Paper ids to compare. Omit for all ingested papers."),
    build_missing_cards: tool.schema.boolean().optional().describe("Generate missing cards before comparing, default false."),
    save_csv: tool.schema.boolean().optional().describe("Save CSV artifact, default true."),
  },
  async execute(args, context) {
    return await runResearchPilot("comparison_table", args, context)
  },
})

export const literature_review = tool({
  description: "Generate a Chinese Markdown literature review using the ResearchPilot backend LLM. If .env is not configured, use prepare_literature_review then save_artifact.",
  args: {
    topic: tool.schema.string().describe("Review topic."),
    paper_ids: tool.schema.array(tool.schema.string()).optional().describe("Paper ids to include. Omit for all ingested papers."),
    build_missing_cards: tool.schema.boolean().optional().describe("Generate missing cards first, default true."),
    save: tool.schema.boolean().optional().describe("Save Markdown artifact, default true."),
  },
  async execute(args, context) {
    return await runResearchPilot("literature_review", args, context)
  },
})

export const prepare_venue_paper_summary = tool({
  description: "Agent-native mode: prepare a CCF venue/journal paper collection for the current OpenCode model to summarize without project API keys.",
  args: {
    collection: tool.schema.object({}).passthrough().optional().describe("Venue paper collection object. If omitted, uses the latest saved collection."),
    collection_json: tool.schema.string().optional().describe("Venue paper collection JSON string."),
    collection_path: tool.schema.string().optional().describe("Path to collection JSON. Defaults to latest saved collection."),
    max_papers: tool.schema.number().optional().describe("Maximum papers to include, default 25."),
    abstract_limit: tool.schema.number().optional().describe("Max abstract characters per paper, default 900."),
    focus: tool.schema.string().optional().describe("Optional focus for the summary."),
  },
  async execute(args, context) {
    return await runResearchPilot("prepare_venue_paper_summary", args, context)
  },
})

export const venue_paper_summary = tool({
  description: "Generate a Chinese Markdown summary of a saved CCF venue/journal collection using the ResearchPilot backend LLM. If .env is absent, use prepare_venue_paper_summary then save_artifact.",
  args: {
    collection: tool.schema.object({}).passthrough().optional().describe("Venue paper collection object. If omitted, uses the latest saved collection."),
    collection_json: tool.schema.string().optional().describe("Venue paper collection JSON string."),
    collection_path: tool.schema.string().optional().describe("Path to collection JSON."),
    max_papers: tool.schema.number().optional().describe("Maximum papers to include, default 25."),
    abstract_limit: tool.schema.number().optional().describe("Max abstract characters per paper, default 900."),
    save: tool.schema.boolean().optional().describe("Save Markdown artifact, default true."),
  },
  async execute(args, context) {
    return await runResearchPilot("venue_paper_summary", args, context)
  },
})

export const metadata_paper_cards = tool({
  description: "Create conservative bilingual metadata-level paper cards from a saved venue/Semantic Scholar collection without downloading PDFs.",
  args: {
    collection: tool.schema.object({}).passthrough().optional().describe("Venue paper collection object. If omitted, uses the latest saved collection."),
    collection_json: tool.schema.string().optional().describe("Venue paper collection JSON string."),
    collection_path: tool.schema.string().optional().describe("Path to collection JSON."),
    topic: tool.schema.string().optional().describe("Topic to write into metadata cards. Defaults to collection topic."),
    paper_indices: tool.schema.array(tool.schema.number()).optional().describe("1-based paper ranks to convert. Omit to use top max_cards."),
    max_cards: tool.schema.number().optional().describe("Number of top collection papers to convert, default 10."),
  },
  async execute(args, context) {
    return await runResearchPilot("metadata_paper_cards", args, context)
  },
})

export const prepare_literature_review = tool({
  description: "Agent-native mode: return cached paper cards and review instructions so the current OpenCode model can write a literature review without project API keys.",
  args: {
    topic: tool.schema.string().describe("Review topic."),
    paper_ids: tool.schema.array(tool.schema.string()).optional().describe("Paper ids to include. Omit for all ingested papers."),
  },
  async execute(args, context) {
    return await runResearchPilot("prepare_literature_review", args, context)
  },
})

export const verify_review = tool({
  description: "Run claim-level citation verification using the ResearchPilot backend LLM. If .env is not configured, use prepare_review_verification then save_claim_verification.",
  args: {
    review_text: tool.schema.string().optional().describe("Review Markdown text. Use this or review_path."),
    review_path: tool.schema.string().optional().describe("Path to review Markdown, absolute or relative to project root."),
    top_k: tool.schema.number().optional().describe("Evidence chunks per claim, default 5."),
    verification_mode: tool.schema.string().optional().describe("strict, balanced, or lenient, default balanced."),
    retrieval_mode: tool.schema.string().optional().describe("bm25 or hybrid, default bm25."),
    paper_ids: tool.schema.array(tool.schema.string()).optional().describe("Paper cards to use for source-aware matching."),
    build_missing_cards: tool.schema.boolean().optional().describe("Build missing paper cards before verifying, default false."),
    diversify_evidence: tool.schema.boolean().optional().describe("Diversify evidence across papers, default true."),
    max_per_paper: tool.schema.number().optional().describe("Max chunks per paper for diverse retrieval, default 2."),
    source_first: tool.schema.boolean().optional().describe("Prioritize source hints when present, default true."),
    source_only_when_available: tool.schema.boolean().optional().describe("Use only matched source paper evidence when source is matched, default true."),
    save: tool.schema.boolean().optional().describe("Save full JSON verification artifact, default true."),
  },
  async execute(args, context) {
    return await runResearchPilot("verify_review", args, context)
  },
})

export const prepare_review_verification = tool({
  description: "Agent-native mode: split a review into candidate claims and retrieve evidence so the current OpenCode model can judge support without project API keys.",
  args: {
    review_text: tool.schema.string().optional().describe("Review Markdown text. Use this or review_path."),
    review_path: tool.schema.string().optional().describe("Path to review Markdown."),
    top_k: tool.schema.number().optional().describe("Evidence chunks per claim, default 5."),
    retrieval_mode: tool.schema.string().optional().describe("bm25 or hybrid, default bm25."),
  },
  async execute(args, context) {
    return await runResearchPilot("prepare_review_verification", args, context)
  },
})

export const save_claim_verification = tool({
  description: "Agent-native mode: validate and save claim verification results produced by the current OpenCode model.",
  args: {
    results: tool.schema.array(tool.schema.object({}).passthrough()).optional().describe("Verification result objects."),
    results_json: tool.schema.string().optional().describe("Verification result JSON list as a string."),
  },
  async execute(args, context) {
    return await runResearchPilot("save_claim_verification", args, context)
  },
})

export const rewrite_review = tool({
  description: "Generate a conservative revised literature review from an original review and saved or provided claim verification results.",
  args: {
    original_review: tool.schema.string().optional().describe("Original review text. Use this or original_review_path."),
    original_review_path: tool.schema.string().optional().describe("Path to original review Markdown."),
    verification_path: tool.schema.string().optional().describe("Path to full verification JSON. Defaults to latest saved verification."),
    verification_results: tool.schema.array(tool.schema.object({}).passthrough()).optional().describe("Inline verification result objects."),
    save: tool.schema.boolean().optional().describe("Save Markdown artifact, default true."),
  },
  async execute(args, context) {
    return await runResearchPilot("rewrite_review", args, context)
  },
})

export const research_ideas = tool({
  description: "Generate future research ideas using the ResearchPilot backend LLM. If .env is not configured, use prepare_research_ideas then save_artifact.",
  args: {
    topic: tool.schema.string().optional().describe("Research topic."),
    paper_ids: tool.schema.array(tool.schema.string()).optional().describe("Paper ids to use. Omit for all ingested papers."),
    build_missing_cards: tool.schema.boolean().optional().describe("Generate missing cards, default false."),
    literature_review: tool.schema.string().optional().describe("Original review text."),
    literature_review_path: tool.schema.string().optional().describe("Path to original review Markdown."),
    revised_literature_review: tool.schema.string().optional().describe("Revised review text."),
    revised_literature_review_path: tool.schema.string().optional().describe("Path to revised review Markdown."),
    verification_path: tool.schema.string().optional().describe("Path to full verification JSON."),
    verification_results: tool.schema.array(tool.schema.object({}).passthrough()).optional().describe("Inline verification result objects."),
    num_ideas: tool.schema.number().optional().describe("Number of ideas, default 5."),
    save: tool.schema.boolean().optional().describe("Save Markdown artifact, default true."),
  },
  async execute(args, context) {
    return await runResearchPilot("research_ideas", args, context)
  },
})

export const prepare_research_ideas = tool({
  description: "Agent-native mode: return paper cards, optional reviews, and verification signals so the current OpenCode model can generate research ideas without project API keys.",
  args: {
    topic: tool.schema.string().optional().describe("Research topic."),
    paper_ids: tool.schema.array(tool.schema.string()).optional().describe("Paper ids to use. Omit for all ingested papers."),
    literature_review: tool.schema.string().optional().describe("Original review text."),
    literature_review_path: tool.schema.string().optional().describe("Path to original review Markdown."),
    revised_literature_review: tool.schema.string().optional().describe("Revised review text."),
    revised_literature_review_path: tool.schema.string().optional().describe("Path to revised review Markdown."),
    verification_path: tool.schema.string().optional().describe("Path to full verification JSON."),
    verification_results: tool.schema.array(tool.schema.object({}).passthrough()).optional().describe("Inline verification result objects."),
    num_ideas: tool.schema.number().optional().describe("Number of ideas, default 5."),
  },
  async execute(args, context) {
    return await runResearchPilot("prepare_research_ideas", args, context)
  },
})

export const save_artifact = tool({
  description: "Agent-native mode: save Markdown or JSON text generated by the current OpenCode model into data/outputs/agent.",
  args: {
    artifact_type: tool.schema.string().describe("Artifact type prefix, e.g. literature_review, revised_literature_review, research_ideas."),
    text: tool.schema.string().optional().describe("Artifact text generated by the agent."),
    path: tool.schema.string().optional().describe("Existing text file to save/copy through the artifact path."),
    suffix: tool.schema.string().optional().describe("File suffix, default .md."),
  },
  async execute(args, context) {
    return await runResearchPilot("save_artifact", args, context)
  },
})

export const watchlist = tool({
  description: "Manage ResearchPilot watchlist or apply it to the latest saved arXiv search results.",
  args: {
    operation: tool.schema.string().describe("One of: list, add, delete, rank_last_search, summarize_last_search."),
    item: tool.schema.object({}).passthrough().optional().describe("Watchlist item for add: name, type, authors, institutions, keywords, notes."),
    index: tool.schema.number().optional().describe("0-based watchlist index for delete."),
    topic: tool.schema.string().optional().describe("Optional topic for summarize_last_search."),
    max_papers: tool.schema.number().optional().describe("Max matched papers for summary, default 8."),
    save: tool.schema.boolean().optional().describe("Save Markdown summary artifact, default true."),
  },
  async execute(args, context) {
    return await runResearchPilot("watchlist", args, context)
  },
})
