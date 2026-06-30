# Stonehenge Wiki Schema

This file defines the maintenance contract for the compiled wiki layer.

## Layers

- `docs/`: raw source files. Do not edit these during compilation.
- `wiki/sources/`: one generated Markdown page per indexed source file.
- `wiki/topics/`: generated topic pages grouped by inferred business tags.
- `wiki/index.md`: generated navigation index.
- `wiki/log.md`: append-only compile and maintenance log.

## Source Page Contract

Each source page must include YAML frontmatter with:

- `title`
- `kind: source`
- `source_path`
- `file_type`
- `tags`
- `comment_count`
- `generated_at`

Each source page should include:

- Summary
- Evidence snippets
- Comments and TODOs

## Operations

- Compile: `./work/skills/stonehenge-wiki/bin/stonehenge-wiki --compile-wiki`
- Lint: `./work/skills/stonehenge-wiki/bin/stonehenge-wiki --lint-wiki`
- API compile: `POST /wiki/compile`
- API lint: `GET /wiki/lint`
