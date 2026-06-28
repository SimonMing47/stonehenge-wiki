---
name: llm-wiki
description: Run the repository-local LLM-wiki system for deterministic document indexing, strict JSON answer generation, Office/code comment and TODO management, best-effort document repair, safe code-result queries, and Permission.json based high-risk command blocking. Use when Codex needs to answer llm-wiki question groups, inspect the wiki index, run an ad-hoc wiki query, or call the CLI from a skill workflow.
---

# LLM Wiki

## Workflow

Use the platform CLI as the source of truth. From the repository root:

```bash
python3 work/main.py --group group-1
```

For all question groups:

```bash
python3 work/main.py
```

For an ad-hoc question:

```bash
python3 work/main.py --ask "统计 docx 文件数量"
```

For an index inspection:

```bash
python3 work/main.py --dump-index
```

For a PowerPoint brief:

```bash
python3 work/main.py --generate-ppt "RAG 知识库建设方案" --slide-count 6
```

For an API service:

```bash
python3 work/main.py --serve
```

Then open `http://127.0.0.1:8765/` for the browser console.

For audit review:

```bash
python3 work/main.py --audit-log --audit-limit 20
```

To compile and validate the persistent Markdown wiki layer:

```bash
python3 work/main.py --compile-wiki
python3 work/main.py --lint-wiki
```

## Safety Rules

Always let the CLI perform safety checks before reading, executing, or repairing target content. It loads `llm-wiki/Permission.json`, blocks denied commands/files/write targets, blocks system/root/keychain password requests, restricts ordinary password retrieval to `docs/02_环境信息`, and returns the required JSON error object for high-risk requests.

## Outputs

Question group answers are written to `llm-wiki/output/<group>-answer.md` as a JSON array. Repair outputs are written under `llm-wiki/output/fixed/`. PowerPoint briefs are written under `llm-wiki/output/presentations/`. Successful runs append a short self-validation line to `result/output.md`. Runtime index and audit data are stored in `llm-wiki/.state/wiki.sqlite`.

## Helper Script

The bundled `scripts/run_llm_wiki.py` wrapper locates the repository root from this skill folder and forwards arguments to `work/main.py`:

```bash
python3 work/skills/llm-wiki/scripts/run_llm_wiki.py --group group-1
```
