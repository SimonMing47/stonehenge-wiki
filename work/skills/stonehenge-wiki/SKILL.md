---
name: stonehenge-wiki
description: Run Stonehenge Wiki via the in-repo skill shell CLI. Use the local REST API only, from Codex or terminal, with a three-step path: configure opencode, compile docs, then ask.
---

# Stonehenge Wiki

## Why this entry

The skill entry for this repository is a shell script:

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki
```

It is a thin HTTP wrapper over the running Stonehenge Wiki service (`http://127.0.0.1:8765` by default).
It does not call Python code directly and does not start the service.

### Environment variables

- `LLM_WIKI_URL`: API base URL, default `http://127.0.0.1:8765`
- `LLM_WIKI_TOKEN`: `X-STONEHENGE-WIKI-TOKEN` header value (optional)
- `LLM_WIKI_ROOT`: default wiki root for `compile`/`ask`
- `OPENCODE_PROVIDER`, `OPENCODE_MODEL`, `OPENCODE_BASE_URL`: optional runtime defaults

## Recommended three-step workflow

The default operational flow is:

1) Configure opencode from local Hermes config (first-time setup)

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki configure-opencode
```

2) Compile markdown knowledge from a real wiki root

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki compile --wiki-root /path/to/stonehenge-wiki
```

3) Ask a question after compile completes

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki ask --wiki-root /path/to/stonehenge-wiki --question-id api-1 --level 简单 "统计 docx 文件数量"
```

You can do all three in one command:

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki quick-start --wiki-root /path/to/stonehenge-wiki --question-id api-1 --level 简单 "统计 docx 文件数量"
```

## Other practical commands

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki health
./work/skills/stonehenge-wiki/scripts/llm-wiki api-contract
```

## LLM Agent Configuration

Recommended operational way is still **agent-based configuration** in `stonehenge-wiki/config.json`.
The default profile uses local `opencode` runtime mode.

If opencode is not installed or lacks Hermes model wiring, run:

```bash
./work/skills/stonehenge-wiki/scripts/configure_opencode_from_hermes.sh
```

That script reads `~/.hermes/.env`, writes key/config under `~/.config/opencode/`, and does not modify repository files.

## Validation sequence

```bash
./work/skills/stonehenge-wiki/scripts/configure_opencode_from_hermes.sh
./work/skills/stonehenge-wiki/scripts/llm-wiki configure-opencode
./work/skills/stonehenge-wiki/scripts/llm-wiki compile --wiki-root /path/to/stonehenge-wiki
./work/skills/stonehenge-wiki/scripts/llm-wiki ask --wiki-root /path/to/stonehenge-wiki "统计 docx 文件数量"
```

Optional API-level checks:

```bash
curl -s http://127.0.0.1:8765/llm/config | python3 -m json.tool
curl -s http://127.0.0.1:8765/health | python3 -m json.tool
```

