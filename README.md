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

## third_party 参考作用
`third_party/` 下各项目仅作为参考，不参与本仓库业务代码修改：

- `paper-qa`：参考证据驱动问答与引用组织方式。
- `gpt-researcher`：参考研究流程编排与检索模块设计。
- `storm`：参考结构化综述与多阶段研究生成思路。
- `litllm`：参考 OpenAI-compatible 模型调用抽象。
- `ScholarLens`：参考学术场景 Streamlit 交互与 RAG 工作流。

本项目不会修改 `third_party/` 下任何文件。
