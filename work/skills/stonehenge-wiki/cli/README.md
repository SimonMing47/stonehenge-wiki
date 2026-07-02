# Stonehenge Wiki Skill CLI

The public CLI for this skill lives under `work/skills/stonehenge-wiki/`.

## Build

Local skill binary:

```bash
./work/scripts/build_skill_cli.sh
```

`build_skill_cli.sh` builds the Rust CLI binaries by target into

- `work/skills/stonehenge-wiki/bin/<os>-<arch>/stonehenge-wiki`

在本机 host 上，脚本会额外维护 `work/skills/stonehenge-wiki/bin/stonehenge-wiki` 作为默认启动入口（指向 host 平台产物）。

Manual build commands (if needed):

```bash
cargo build --release --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --bin stonehenge-wiki-linux
```

Windows release entry:

```powershell
cargo build --release --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --target x86_64-pc-windows-gnu --bin stonehenge-wiki-windows
```

## Use

The API service must already be running. The CLI defaults to `http://127.0.0.1:8765`.

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --help
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --health
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --ask "统计 docx 文件数量"
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --url http://127.0.0.1:8765 --list-sources
```

The CLI only calls the REST API. It does not start the REST service or execute local project code.
