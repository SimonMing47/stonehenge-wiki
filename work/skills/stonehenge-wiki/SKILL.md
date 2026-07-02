---
name: stonehenge-wiki
description: Run the repository-local Stonehenge Wiki system for deterministic document indexing, strict JSON answer generation, Office/code comment and TODO management, best-effort document repair, safe code-result queries, and Permission.json based high-risk command blocking. Use when Codex needs to answer stonehenge-wiki question groups, inspect the wiki index, run an ad-hoc wiki query, or call the CLI from a skill workflow.
---

# Stonehenge Wiki

## Workflow

Use the bundled Rust CLI as the source of truth. From the repository root, build it once when needed:

```bash
./work/skills/stonehenge-wiki/scripts/build_skill_cli.sh
```

The REST CLI entrypoint is:

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --url http://127.0.0.1:8765 --group group-1
```

For all question groups:

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki
```

For an ad-hoc question:

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --ask "统计 docx 文件数量"
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --explain-ask "SQLite SELECT 命令是什么"
```

For an index inspection:

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --dump-index
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-sources
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-source-versions
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --source-history "docs/03_学习材料/Knowledge-Notes.md"
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-wiki-sections --wiki-section-limit 20
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --search-wiki "SQLite SELECT" --wiki-section-limit 5
```

For source ingestion:

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --import-source ./docs/source.pdf --import-title "知识库评估材料" --import-category 03_学习材料
```

For a workbench brief:

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --generate-brief "企业知识库建设方案" --slide-count 6
```

For API access, make sure the Stonehenge Wiki REST service is already running, then call:

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --url http://127.0.0.1:8765 --health
```

Then open `http://127.0.0.1:8765/` for the browser console.

## LLM Agent Configuration

Configure LLMs as named agents in `stonehenge-wiki/config.json`, not as one shared untracked shell setting. The runtime reads `llm.agents`, chooses `llm.default_agent`, and can route categories through `llm.category_agents`.

The default local profile is:

- `default_agent`: `opencode`
- `agents.opencode.provider`: `opencode-hermes-deepseek`
- `agents.opencode.model`: `deepseek-v4-pro`
- `agents.opencode.base_url`: `https://api.deepseek.com/v1`
- `agents.opencode.api_key_env`: `DEEPSEEK_API_KEY`
- `agents.opencode.env_file`: `~/.hermes/.env`

If opencode is missing, install it with the official installer, then source the shell profile:

```bash
command -v opencode >/dev/null || curl -fsSL https://opencode.ai/install | bash
source ~/.zshrc >/dev/null 2>&1 || true
opencode --version
```

If opencode has no LLM configured, copy only the Hermes DeepSeek key into a local 0600 key file and point `~/.config/opencode/opencode.json` at it with `{file:~/.config/opencode/hermes-deepseek.key}`. Do not store API keys in the repository.

Validate agent wiring before answering LLM-backed questions:

```bash
opencode models hermes-deepseek
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --url http://127.0.0.1:8765 --health
curl -s http://127.0.0.1:8765/llm/config | python3 -m json.tool
```

The Rust CLI remains a REST API client. It must not call Python or opencode directly.

For audit review:

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --audit-log --audit-limit 20
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --governance-report
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --evaluation-report --group group-1
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --readiness-report --group group-demo
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --export-release-bundle --group group-demo
```

To compile, inspect, search, and validate the persistent Markdown wiki layer:

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --compile-wiki
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-wiki-sections --wiki-section-limit 20
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --search-wiki "SQLite SELECT" --wiki-section-limit 5
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --lint-wiki
```

## Safety Rules

Always let the CLI perform safety checks before reading, executing, or repairing target content. It calls the Stonehenge Wiki REST API, which loads `stonehenge-wiki/Permission.json`, blocks denied commands/files/write targets, blocks system/root/keychain password requests, restricts ordinary password retrieval to `docs/02_环境信息`, and returns the required JSON error object for high-risk requests. For HTTP calls, `stonehenge-wiki/.env` or the process environment can provide tokens: `STONEHENGE_WIKI_READ_TOKEN` is read-only and `STONEHENGE_WIKI_API_TOKEN` is the admin token for imports, reindexing, compilation, group runs, and workbench brief generation.

## Outputs

Imported sources are copied under `stonehenge-wiki/docs/<category>/` and reindexed. Question group answers are written to `stonehenge-wiki/output/<group>-answer.md` as a JSON array. Repair outputs are written under `stonehenge-wiki/output/fixed/`. Workbench briefs are written under `stonehenge-wiki/output/presentations/`. Governance reports are written under `stonehenge-wiki/output/reports/`. Successful runs append a short self-validation line to `result/output.md`. Runtime index, source registry, metadata-only source version history, compiled wiki section index, and audit data are stored in `stonehenge-wiki/.state/wiki.sqlite`.

## Platform Builds

The skill includes platform-specific Rust entrypoints for packaging:

```bash
cargo build --release --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --bin stonehenge-wiki-linux
cargo build --release --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --bin stonehenge-wiki-windows
```
