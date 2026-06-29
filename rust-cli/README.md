# LLM-Wiki Rust CLI (平台差异入口)

这个目录提供一个 Rust 封装的 CLI 入口，默认把命令透传给现有的 Python 核心 CLI（`work/main.py`），用于在 Windows 和 Linux 下提供独立可执行文件。

## 可执行文件

- Linux: `llm-wiki-linux`
- Windows: `llm-wiki-windows`（Windows 下实际文件为 `llm-wiki-windows.exe`）

两个入口共用同一套 Rust 命令透传逻辑，仅在 Python 解释器选择上做平台区分：
- Linux/Unix: 优先 `python3`
- Windows: 优先 `python`

## 构建

### Linux

```bash
cd rust-cli
cargo build --release --bin llm-wiki-linux
```

### Windows

```powershell
cd rust-cli
cargo build --release --bin llm-wiki-windows
```

## 使用

Linux 示例：

```bash
cd rust-cli
./target/release/llm-wiki-linux --help
./target/release/llm-wiki-linux --ask "统计 docx 文件数量"
./target/release/llm-wiki-linux --group group-1
./target/release/llm-wiki-linux --serve --host 127.0.0.1 --port 8765
```

Windows 示例：

```powershell
cd rust-cli
./target/release/llm-wiki-windows.exe --help
./target/release/llm-wiki-windows.exe --ask "统计 docx 文件数量"
./target/release/llm-wiki-windows.exe --group group-1
./target/release/llm-wiki-windows.exe --serve --host 127.0.0.1 --port 8765
```

## 环境变量

- `LLM_WIKI_MAIN_PY`: 指定 `work/main.py` 的完整路径（可选）
- `LLM_WIKI_ROOT`: 指定 `llm-wiki/` 根目录，CLI 会自动寻找 `work/main.py`
- `LLM_WIKI_PYTHON`: 指定 Python 可执行路径（可选）

所有参数均透传给 Python CLI，支持与 `python3 work/main.py` 相同的参数集合与行为。
