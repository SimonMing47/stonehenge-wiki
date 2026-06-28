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
- `wiki/` 是参考 Karpathy LLM Wiki 思路新增的编译型 Markdown 知识层：`docs/` 保留原始来源，`wiki/` 保存可维护知识页，`AGENTS.md` 定义 schema。
- CLI、Codex skill、HTTP API、浏览器控制台共用同一套平台核心，避免规则分叉。
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

来源注册表：

```bash
python3 work/main.py --list-sources
python3 work/main.py --list-sources --include-missing-sources
python3 work/main.py --list-source-versions
python3 work/main.py --source-history docs/03_学习材料/RAG-Notes.md
```

重建并持久化索引：

```bash
python3 work/main.py --reindex
```

导入知识源并自动重建索引：

```bash
python3 work/main.py --import-source ./docs/source.pdf --import-title "RAG 评估材料" --import-category 03_学习材料
```

查看审计日志：

```bash
python3 work/main.py --audit-log --audit-limit 20
```

治理报告：

```bash
python3 work/main.py --governance-report
python3 work/main.py --export-governance-report
```

编译 Markdown wiki：

```bash
python3 work/main.py --compile-wiki
```

检查 Markdown wiki：

```bash
python3 work/main.py --lint-wiki
```

启动 HTTP API：

```bash
python3 work/main.py --serve
```

启动后打开控制台：

```text
http://127.0.0.1:8765/
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
- `GET /`：浏览器控制台
- `GET /index`：文件、批注和持久化状态
- `GET /sources?include_missing=1`：来源注册表，包含 origin、hash、大小、状态和最后索引时间
- `GET /sources/history?path=docs/03_学习材料/RAG-Notes.md`：来源版本历史，只记录路径、hash、大小和观测次数，不复制原始正文
- `GET /audit?limit=50`：审计事件
- `GET /wiki/lint`：检查编译型 Markdown wiki
- `GET /reports/governance`：治理报告 JSON，包含来源状态、TODO 风险、审计阻断和任务历史
- `GET /files/output/...`：下载生成物，例如 PPTX
- `POST /ask`：单问，JSON body 示例 `{"id":"api-1","title":"统计 docx 文件数量","level":"简单"}`
- `POST /groups/run`：运行题组，JSON body 示例 `{"groups":["group-1"]}`
- `POST /sources/import`：导入本地文件或公开 URL，JSON body 示例 `{"source":"https://example.com/page.html","title":"网页资料","category":"00_inbox"}`
- `POST /slides/generate`：生成 PPTX，JSON body 示例 `{"topic":"RAG 知识库建设方案","slide_count":6}`
- `POST /reports/governance/export`：导出 Markdown 治理报告到 `output/reports/`
- `POST /reindex`：重建索引
- `POST /wiki/compile`：将 `docs/` 编译为 `wiki/` Markdown 知识层

导入接口会落盘到 `docs/<category>/`，支持 pdf、doc/docx、ppt/pptx、xls/xlsx、html、xml、md、代码和常见文本格式；私网、localhost、超大文件和 `Permission.json` 拒绝的路径会被阻断并记录审计。

如果设置了 `LLM_WIKI_API_TOKEN` 或 `LLM_WIKI_READ_TOKEN`，请求需携带 `X-LLM-WIKI-TOKEN`。`LLM_WIKI_READ_TOKEN` 可访问 `/index`、`/sources`、`/sources/history`、`/audit`、`/wiki/lint`、`/reports/governance`、`/files/...` 和 `/ask`；`LLM_WIKI_API_TOKEN` 是管理 token，可调用所有接口，包括导入、重建索引、编译 wiki、运行题组、生成 PPT 和导出治理报告。控制台右上角的 `API token` 输入框会把 token 保存到浏览器本地存储并随请求发送。

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
- 来源注册表会记录 metadata-only 版本历史，包含路径、SHA-256、大小、首次/末次观测时间和观测次数
- 高危命令统一返回 `{"error_msg":"高危命令，拒绝访问"}`
