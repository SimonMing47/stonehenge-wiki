---
name: stonehenge-wiki
description: Run LLM Wiki through its local REST wrapper with an OpenCode runtime.
---

# LLM Wiki OpenCode workflow

The public script entry is:

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki
```

It calls the local REST service at `http://127.0.0.1:8765`. It does not read source documents directly and does not start the service.

## Runtime configuration

The evaluation image is expected to expose `opencode` in `PATH`. Preserve an existing platform configuration, or create one from `OPENCODE_API_KEY`:

```bash
export OPENCODE_API_KEY='<injected by the runtime>'
export OPENCODE_PROVIDER='zhipu'
export OPENCODE_MODEL='glm-5.2'
export OPENCODE_BASE_URL='https://open.bigmodel.cn/api/coding/paas/v4'
./work/skills/stonehenge-wiki/scripts/configure_opencode.sh
```

The credential is stored outside the repository with mode `0600`.

## Data root

When `--wiki-root` is omitted, both the service and wrapper prefer `/app/code/judge-assets/01_01_llm_wiki/`, then the `llm-wiki/` directory next to `work/`. The checked-in `stonehenge-wiki/` fixture is a development fallback. `LLM_WIKI_ROOT` overrides discovery.

## Commands

```bash
./work/scripts/server.sh start
./work/skills/stonehenge-wiki/scripts/llm-wiki configure-opencode
./work/skills/stonehenge-wiki/scripts/llm-wiki compile
./work/skills/stonehenge-wiki/scripts/llm-wiki ask --question-id api-1 --level 简单 '统计 docx 文件数量'
./work/skills/stonehenge-wiki/scripts/llm-wiki health
./work/skills/stonehenge-wiki/scripts/llm-wiki api-contract
```

Environment variables:

- `LLM_WIKI_URL`: REST base URL
- `LLM_WIKI_TOKEN`: optional API token
- `LLM_WIKI_ROOT`: explicit data root
- `OPENCODE_PROVIDER`, `OPENCODE_MODEL`, `OPENCODE_BASE_URL`: runtime model settings
- `OPENCODE_RUNTIME_COMMAND`: command used by the Python backend
