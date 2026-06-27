# LLM-Wiki-System 运行说明

## 环境

- Python 3.11.0
- 必需依赖：无
- 推荐依赖：`openpyxl`，用于更完整地读取 Excel 单元格批注并生成透视表/透视图文件
- 推荐外部程序：LibreOffice / `soffice`，用于 `.doc/.ppt/.xls` 老式 Office 文件转换、索引和修复

安装推荐依赖：

```bash
python3 -m pip install openpyxl
```

安装 LibreOffice 后，确保命令行可访问 `soffice` 或 `libreoffice`。

## 目录

评测运行时，`work/` 同级应存在 `llm-wiki/`：

```text
llm-wiki/
  docs/
  question/
  output/
  Permission.json
work/
  main.py
  llm_wiki/
result/
  output.md
```

## 平台能力

本作品不是单次脚本，而是一个企业级 LLM-wiki 平台骨架：

- `LLMWikiPlatform` 统一承载索引、安全、问答、修复、审计和任务运行。
- `SQLiteStore` 将可重建索引、批注表、审计事件、任务运行记录持久化到 `llm-wiki/.state/wiki.sqlite`。
- CLI、Codex skill、HTTP API 共用同一套平台核心，避免规则分叉。
- API 可通过环境变量 `LLM_WIKI_API_TOKEN` 开启 `X-LLM-WIKI-TOKEN` 鉴权。

## CLI 入口

处理 `llm-wiki/question/` 下全部 `group-*.md`：

```bash
python3 work/main.py
```

处理指定题组：

```bash
python3 work/main.py --group group-1
```

指定 wiki 目录：

```bash
python3 work/main.py --wiki-root /path/to/llm-wiki --group group-1
```

单问调试：

```bash
python3 work/main.py --ask "统计 docx 文件数量"
```

索引检查：

```bash
python3 work/main.py --dump-index
```

重建并持久化索引：

```bash
python3 work/main.py --reindex
```

查看审计日志：

```bash
python3 work/main.py --audit-log --audit-limit 20
```

启动 HTTP API：

```bash
python3 work/main.py --serve
```

启动指定端口：

```bash
python3 work/main.py --serve --host 127.0.0.1 --port 8765
```

自验证：

```bash
python3 work/main.py --self-test
```

开发验证：

```bash
python3 -m compileall -q work
PYTHONPATH=work python3 -m unittest discover -s work/tests -v
```

## HTTP API

默认监听 `127.0.0.1:8765`。

- `GET /health`：健康检查和索引统计
- `GET /index`：文件、批注和持久化状态
- `GET /audit?limit=50`：审计事件
- `POST /ask`：单问，JSON body 示例 `{"id":"api-1","title":"统计 docx 文件数量","level":"简单"}`
- `POST /groups/run`：运行题组，JSON body 示例 `{"groups":["group-1"]}`
- `POST /reindex`：重建索引

## Skill 调用

仓库内置 Codex skill 位于：

```text
work/skills/llm-wiki/
```

可直接通过 wrapper 调用 CLI：

```bash
python3 work/skills/llm-wiki/scripts/run_llm_wiki.py --group group-1
```

如需安装到本机 Codex，可将 `work/skills/llm-wiki` 复制到 `${CODEX_HOME:-$HOME/.codex}/skills/`。

## 输出约定

- 答案写入 `llm-wiki/output/<group>-answer.md`
- 修复文件写入 `llm-wiki/output/fixed/`
- 成功运行日志追加到 `result/output.md`
- 运行状态、索引、审计写入 `llm-wiki/.state/wiki.sqlite`
- 高危命令统一返回 `{"error_msg":"高危命令，拒绝访问"}`
