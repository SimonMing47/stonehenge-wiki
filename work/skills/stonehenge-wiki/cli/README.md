# LLM Wiki REST wrapper

The competition runtime uses the shell wrapper as its public API client:

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki
```

Start the service first, then configure OpenCode, compile and ask:

```bash
./work/scripts/server.sh start
./work/skills/stonehenge-wiki/scripts/llm-wiki configure-opencode
./work/skills/stonehenge-wiki/scripts/llm-wiki compile
./work/skills/stonehenge-wiki/scripts/llm-wiki ask '统计 docx 文件数量'
```

The wrapper auto-discovers the `llm-wiki/` directory next to `work/`. Use `LLM_WIKI_ROOT` or `--wiki-root` to override it. Rust/Cargo is not required at evaluation runtime.
