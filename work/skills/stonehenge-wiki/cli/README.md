# Stonehenge Wiki Skill Wrapper CLI

This skill uses a **shell wrapper CLI** as the primary call path:

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki
```

## Usage

The API service must already be running. The wrapper defaults to `http://127.0.0.1:8765`.

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki configure-opencode
./work/skills/stonehenge-wiki/scripts/llm-wiki compile --wiki-root /path/to/stonehenge-wiki
./work/skills/stonehenge-wiki/scripts/llm-wiki ask --wiki-root /path/to/stonehenge-wiki "统计 docx 文件数量"
./work/skills/stonehenge-wiki/scripts/llm-wiki quick-start --wiki-root /path/to/stonehenge-wiki --question-id api-1 --level 简单 "统计 docx 文件数量"
./work/skills/stonehenge-wiki/scripts/llm-wiki health
```

### Notes

- This wrapper does not require Rust/Cargo at runtime and does not start services.
