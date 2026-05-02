# ResearchPilot

## 项目目标
ResearchPilot 是一个端到端 AI Research Assistant 课程项目，目标是逐步实现：

1. 上传 PDF
2. 解析 PDF 并切分为可检索 chunks
3. 构建混合检索系统（BM25 + 向量检索）
4. 生成带证据引用的问答结果
5. 生成论文卡片
6. 生成文献综述
7. 进行 claim-level citation verification
8. 后续可选：论文搜索与 watchlist

当前仓库仅包含最小骨架，不含业务逻辑实现。

## 目录结构
```text
research-pilot/
  app/
    streamlit_app.py
  researchpilot/
    __init__.py
    config.py
    schemas.py
    llm/
      __init__.py
      openai_client.py
    ingest/
      __init__.py
      pdf_parser_pymupdf.py
      chunker.py
      pipeline.py
    retrieval/
      __init__.py
      bm25_index.py
      vector_index.py
      hybrid_retriever.py
    qa/
      __init__.py
      answer_with_citations.py
    cards/
      __init__.py
      paper_card_generator.py
    review/
      __init__.py
      lit_review_generator.py
    verify/
      __init__.py
      claim_verifier.py
    storage/
      __init__.py
      corpus_store.py
  data/
    uploads/
    chunks/
    indices/
    outputs/
  scripts/
  tests/
  requirements.txt
  .env.example
  README.md
```

## MVP 计划（最小可交付）
- 阶段 1：打通单页 Streamlit 入口与项目配置。
- 阶段 2：实现 PDF 入库、解析、chunk 存储。
- 阶段 3：实现混合检索与带引用问答。
- 阶段 4：补充论文卡片、综述和 claim 级引用验证。

## Smoke test: PDF parsing
运行命令：

```bash
python scripts/smoke_parse_pdf.py data/uploads/example.pdf
```

成功标准：
- 不需要 `.env`。
- 不调用 LLM。
- 给一篇 PDF 后，能打印 page 数、chunk 数和 first chunk preview。

## Smoke test: BM25 retrieval
运行命令：

```bash
python scripts/smoke_bm25.py data/uploads/example.pdf "program alignment"
```

成功标准：
- 能打印 top-k chunks。
- 不需要 `.env`。
- 不调用 LLM。

## Smoke test: vector retrieval
运行命令：

```bash
python scripts/smoke_vector.py data/uploads/example.pdf "program alignment"
```

说明：
- 第一次运行可能会下载 sentence-transformers 模型。

成功标准：
- 能打印 top-k chunks。
- 不需要 `.env`。
- 不调用 LLM。

## Smoke test: hybrid retrieval
运行命令：

```bash
python scripts/smoke_hybrid.py data/uploads/example.pdf "program alignment"
```

说明：
- Hybrid retrieval combines BM25 keyword retrieval and vector semantic retrieval.

成功标准：
- 能打印 top-k chunks。
- 不需要 `.env`。
- 不调用 LLM。

## Smoke test: LLM client
先创建 `.env`：

```bash
cp .env.example .env
```

然后设置：

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
```

运行：

```bash
python scripts/smoke_llm.py "hello"
```

提醒：
- The client uses OpenAI-compatible chat completions.
- Do not use /v1/completions with messages.

## Smoke test: RAG QA
运行命令：

```bash
python scripts/smoke_rag_qa.py data/uploads/example.pdf "这篇论文主要解决什么问题？"
```

成功标准：
- 能返回中文回答。
- 回答中包含 [E1] / [E2] 形式的 evidence citation。
- 末尾或下方能看到 evidence chunks 的 paper_id、page、preview。

## Smoke test: paper card generation
运行命令：

```bash
python scripts/smoke_paper_card.py data/uploads/example.pdf
```

成功标准：
- 输出合法 JSON 或可读 dict。
- 包含 problem / method / contribution / limitation / future_work 等字段。
- 需要配置 `.env`。

## Smoke test: arXiv paper search
运行命令：

```bash
python scripts/smoke_arxiv_search.py "program equivalence checking semantic alignment" --max-results 5
```

下载第一个搜索结果 PDF：

```bash
python scripts/smoke_arxiv_search.py "program equivalence checking semantic alignment" --max-results 5 --download-first
```

说明：
- This step uses arXiv search only.
- It does not call the LLM.
- It does not automatically ingest the downloaded PDF yet.
- arXiv API has rate limits.
- If HTTP 429 occurs, wait a few minutes and retry.
- The code uses a 3-second client delay and small page size.

成功标准：
- 能打印 arXiv 搜索结果。
- 加 `--download-first` 后能下载 PDF 到 `data/uploads/`。
- 不需要 `.env`。

## Run Streamlit app
运行命令：

```bash
streamlit run app/streamlit_app.py --server.fileWatcherType none
```

说明：
- 需要先配置 `.env` 才能问答。
- 上传的 PDF 保存在 `data/uploads/`。
- Search Papers tab 支持 arXiv topic search。
- Watchlist tab 支持添加 professor / research group / institution / keywords 关注对象。
- Search Papers tab 会基于 watchlist 对 arXiv 结果打分，并解释推荐原因。
- Watchlist Trend Summary 可总结关注对象相关论文趋势。
- 当前版本仅基于 arXiv metadata 和本地 watchlist；future work 可接 Semantic Scholar / OpenAlex author and institution graph。
- 用户可以勾选搜索结果中的论文并下载 PDF。
- 可选择自动 ingest 下载后的 PDFs 到当前知识库。
- Paper Cards tab 可为已入库论文生成结构化论文卡片。
- Paper Cards tab 可以自动汇总已生成的 paper cards，形成 comparison table。
- 支持下载 comparison table CSV（`paper_comparison.csv`）。
- Literature Review tab 可以基于已生成的 paper cards 生成结构化综述。
- Literature Review tab 支持 claim-level citation verification。
- 系统会把综述拆成 claims，并检索 evidence 判断 supported / weakly_supported / unsupported。
- 当前最多验证前 12 条 claims，以控制运行时间。
- weakly_supported / unsupported claims 会显示 conservative rewrite suggestion。
- 系统不会自动改写原文，只提供人工参考。
- 系统支持 Verified Literature Review Rewrite。
- 该功能基于 claim verification 和 conservative rewrite suggestions 生成修订版综述。
- Research Ideas tab 可以基于 paper cards、综述、claim verification 和 revised review 生成未来研究方向。
- 该功能不会声称 ideas 一定原创，只生成候选研究假设，仍需人工判断和进一步调研。
- 原始综述不会被覆盖，用户可以同时比较 original 和 revised versions。
- 系统支持 review version history（v0/v1/v2...）。
- 用户可以对任意版本进行 claim verification，并基于当前版本继续生成下一版 revised review。
- 系统支持 original vs revised side-by-side comparison 和 text diff。
- 综述支持下载 markdown（`literature_review.md`）。
- 修订版综述支持下载 markdown（`revised_literature_review.md`）。
- 当前版本为 in-memory pipeline，重启 app 后需要重新 ingest。
- Paper cards 当前保存在 session_state 中，重启 app 后需要重新生成。
- 当前综述保存在 session_state 中，重启 app 后需要重新生成。
- 当前修订版综述保存在 session_state 中，重启 app 后需要重新生成。

成功标准：
- `streamlit run app/streamlit_app.py` 能打开页面。
- 用户能上传 PDF。
- 用户能提问。
- 用户能在 Paper Cards tab 选择论文并生成 card。
- card 以 JSON 和 markdown 形式显示。
- 用户能在 Literature Review tab 基于 paper cards 生成结构化中文综述。
- 用户能下载 `literature_review.md`。
- 用户可以对 v0、v1、v2 等版本做多轮 verify-rewrite 循环。
- 用户可以 side-by-side 对比两个版本并查看 text diff。
- v0 original 始终保留，不会被覆盖。
- 返回回答包含 [E1]/[E2]。
- evidence chunks 能展开查看。

## third_party 参考作用
`third_party/` 下各项目仅作为参考，不参与本仓库业务代码修改：

- `paper-qa`：参考证据驱动问答与引用组织方式。
- `gpt-researcher`：参考研究流程编排与检索模块设计。
- `storm`：参考结构化综述与多阶段研究生成思路。
- `litllm`：参考 OpenAI-compatible 模型调用抽象。
- `ScholarLens`：参考学术场景 Streamlit 交互与 RAG 工作流。

本项目不会修改 `third_party/` 下任何文件。
