# Stonehenge Wiki PR

## Summary

- What changed:
- Why it matters:
- Owner area: Platform/API/Security | Web Console/Product | CLI/Skill/Quality/Release

## Impact

- API or contract impact:
- CLI or skill impact:
- Web Console impact:
- Security/auth/audit impact:
- Data or migration impact:
- Release bundle or generated artifact impact:

## Architecture Checks

- [ ] Preserves no-RAG architecture; retrieval remains on compiled wiki / `wiki_sections`.
- [ ] Rust CLI remains REST-only and does not call Python or opencode directly.
- [ ] API, CLI, Web, and skill behavior stay aligned.
- [ ] Raw source handling does not expose secrets or package original `docs/` into release bundles.

## Verification

Run the checks that apply and paste the result summary.

- [ ] `python3 -m compileall -q work`
- [ ] `PYTHONPATH=work python3 -m stonehenge_wiki.contract_checks`
- [ ] `PYTHONPATH=work python3 -m unittest discover -s work/tests -q`
- [ ] `cargo fmt --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --check`
- [ ] `cargo test --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml`
- [ ] `./work/skills/stonehenge-wiki/scripts/build_skill_cli.sh`
- [ ] Browser smoke on `http://127.0.0.1:8765/` when UI changes.
- [ ] Release smoke when readiness/evaluation/release bundle changes.

## Evidence

- Screenshots or recordings:
- API/CLI output:
- GitHub Actions run:

## Review Routing

- API/schema/security changes: Platform owner + Quality owner.
- UI changes: Web owner + Platform API check + Quality check.
- CLI/skill/release changes: Quality owner + Platform API check.
- Docs-only changes: one reviewer; two reviewers if security or release behavior changes.
