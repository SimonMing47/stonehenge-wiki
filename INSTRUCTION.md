# stonehenge-wiki 运行说明

## 环境

- 对外入口：`work/skills/stonehenge-wiki/scripts/llm-wiki`（skill 脚本 CLI）
- 构建依赖：无需 Rust/Cargo（脚本调用方式不依赖本地 Rust 二进制）
- 推荐依赖：`openpyxl`，用于更完整地读取 Excel 单元格批注并生成透视表/透视图文件
- 推荐外部程序：LibreOffice / `soffice`，用于 `.doc/.ppt/.xls` 老式 Office 文件转换、索引和修复

安装 LibreOffice 后，确保命令行可访问 `soffice` 或 `libreoffice`。

## 目录

评测运行时，`work/` 同级应存在 `stonehenge-wiki/`：

```text
stonehenge-wiki/
  docs/
  question/
  output/
  Permission.json
work/
  main.py
  stonehenge_wiki/
result/
  output.md
```

## 平台能力

本作品不是单次脚本，而是一个企业级 LLM-wiki 平台骨架：

- `StonehengeWikiPlatform` 统一承载索引、安全、问答、修复、审计和任务运行。
- `SQLiteStore` 将可重建索引、批注表、审计事件、任务运行记录持久化到 `stonehenge-wiki/.state/wiki.sqlite`。
- `wiki/` 是参考 Karpathy LLM Wiki 思路新增的编译型 Markdown 知识层：`docs/` 保留原始来源，`wiki/` 保存可维护知识页，`AGENTS.md` 定义 schema。
- CLI、Codex skill、HTTP API、浏览器控制台共用同一套平台核心，避免规则分叉。
- API 可通过 `stonehenge-wiki/.env` 或环境变量配置 `STONEHENGE_WIKI_API_TOKEN` / `STONEHENGE_WIKI_READ_TOKEN`，开启 `X-STONEHENGE-WIKI-TOKEN` 分级鉴权。

## CLI 入口（推荐：skill 脚本）

系统默认 CLI 入口统一为 skill 脚本（不再以 Rust 二进制作为第一入口）：

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki
```

该脚本是 HTTP wrapper，只调用 `127.0.0.1:8765` 的 REST API，不直接调用 Python，也不直接调用 opencode。

### 环境参数

- `LLM_WIKI_URL`：服务地址（默认 `http://127.0.0.1:8765`）
- `LLM_WIKI_TOKEN`：`X-STONEHENGE-WIKI-TOKEN`
- `LLM_WIKI_ROOT`：默认的 `--wiki-root`

### 系统初始化与调用（最小流程）

1）配置 opencode（从本机 Hermes 配置读取可用的密钥，优先 `OPENCODE_API_KEY`，找不到再尝试 `OPENAI_API_KEY` / `DEEPSEEK_API_KEY`）

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki configure-opencode
```

2）编译知识（传入真实的 `stonehenge-wiki` 根目录）

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki compile --wiki-root /path/to/stonehenge-wiki
```

3）编译完成后提问

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki ask --wiki-root /path/to/stonehenge-wiki --question-id api-1 --level 简单 "统计 docx 文件数量"
```

一键执行（配置 + 编译 + 提问）：

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki quick-start --wiki-root /path/to/stonehenge-wiki --question-id api-1 --level 简单 "统计 docx 文件数量"
```

健康检查和能力核验：

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki health
./work/skills/stonehenge-wiki/scripts/llm-wiki api-contract
```

服务端如果未启动，可先用：

```bash
./work/scripts/server.sh start
```

REST API 服务启动后打开控制台：

```text
http://127.0.0.1:8765/
```

服务生命周期管理脚本（建议默认用这个）：

```bash
./work/scripts/server.sh start
./work/scripts/server.sh status
./work/scripts/server.sh inspect
./work/scripts/server.sh stop
./work/scripts/server.sh restart
./work/scripts/server.sh tail

./work/scripts/health_check.sh
```

`server.sh status` 返回码：`0=ok`、`1=degraded`、`2=blocked`。`health_check.sh` 会透传同一返回码，适合用于 CI 健康闸门。

可用环境变量：`STONEHENGE_WIKI_HOST` / `STONEHENGE_WIKI_PORT` / `STONEHENGE_WIKI_ROOT`，也可通过 `--host`、`--port`、`--wiki-root` 显式覆盖参数。

检查 REST API：

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki health
./work/skills/stonehenge-wiki/scripts/llm-wiki api-contract
```

REST 自验证：

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki health
```

## 本地交付一致性与质量检查

文档、CLI 与 API 对齐变更后，建议执行以下检查：

```bash
python3 scripts/check_doc_consistency.py
PYTHONPATH=work python3 -m stonehenge_wiki.contract_checks
PYTHONPATH=work python3 -m unittest discover -s work/tests -q
```

该命令链对应三类质量门：

- `scripts/check_doc_consistency.py`：检查 `README/INSTRUCTION/DESIGN` 文档与 CLI 实现/API 契约一致性
- `contract_checks`：检查 API route / scope / query / body / CLI 接口映射一致性
- 单元测试：覆盖服务、治理、审计和文件服务回归

- `PYTHONPATH=work` 的设置请与项目里运行 `unit test` 的方式保持一致。

## LLM Agent 与 opencode 配置

LLM 配置必须按 agent 隔离，不要把所有模型参数只堆在顶层 `llm` 字段里。`stonehenge-wiki/config.json` 的约定如下：

- `llm.agents.<name>`：一个可独立启停、独立 provider/model/env 的 agent 配置。
- `llm.default_agent`：默认问答、题组运行和工作台生成使用的 agent。
- `llm.category_agents`：按知识类别路由到指定 agent，例如 `03_学习材料` 使用 `opencode`。
- 顶层 `llm.provider/model/base_url/api_key_env/env_file` 保留为兼容字段，也会作为 agent 的 fallback。

当前默认 runtime 是 `opencode`，默认配置不预置某个具体模型名：

```json
{
  "llm": {
    "enabled": true,
    "default_agent": "opencode",
    "agents": {
      "opencode": {
        "enabled": true,
        "provider": "opencode-runtime",
        "model": "",
        "base_url": "",
        "api_key_env": "",
        "env_file": "",
        "timeout_seconds": 120,
        "max_context_chars": 16000,
        "max_tokens": 900,
        "temperature": 0.1
      }
    }
  }
}
```

如果本机还没有 opencode，或 opencode 没有 LLM provider 配置，直接使用 skill 脚本从本机 Hermes 配置中抽取可用 API：

```bash
./work/skills/stonehenge-wiki/scripts/configure_opencode_from_hermes.sh
```

脚本会执行三件事：

- 如果 `opencode` 不存在，则安装到 `~/.opencode/bin`，并复用 shell 中已有的 PATH 配置。
- 从 `~/.hermes/.env` 读取可用密钥（默认优先 `OPENCODE_API_KEY`，找不到再尝试 `OPENAI_API_KEY` / `DEEPSEEK_API_KEY`），写入 `~/.config/opencode/opencode-runtime.key`，权限固定为 `0600`。
- 写入 `~/.config/opencode/opencode.json`，使用 provider `opencode-runtime`（模型名称可按实际环境定制）。

手工配置时也遵循同样约定。密钥文件只放在用户目录，不提交到仓库：

```bash
mkdir -p ~/.config/opencode
grep -E '^(OPENCODE_API_KEY|OPENAI_API_KEY|DEEPSEEK_API_KEY)=' ~/.hermes/.env | head -n 1 | cut -d= -f2- > ~/.config/opencode/opencode-runtime.key
chmod 600 ~/.config/opencode/opencode-runtime.key
```

`~/.config/opencode/opencode.json` 应使用 OpenAI-compatible provider，并通过 `{file:...}` 引用密钥文件：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "opencode-runtime/default",
  "small_model": "opencode-runtime/default",
  "provider": {
    "opencode-runtime": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Opencode Runtime",
      "options": {
        "baseURL": "",
        "apiKey": "{file:~/.config/opencode/opencode-runtime.key}"
      },
      "models": {
        "default": {
          "name": "Runtime model",
          "limit": {
            "context": 16000,
            "output": 900
          }
        }
      }
    }
  },
  "enabled_providers": ["opencode-runtime"]
}
```

验证顺序：

```bash
opencode --version
opencode models opencode-runtime
opencode run --pure --format json "只回复 OK"
python3 -m json.tool stonehenge-wiki/config.json >/dev/null
./work/skills/stonehenge-wiki/scripts/llm-wiki health
curl -s http://127.0.0.1:8765/llm/config | python3 -m json.tool
./work/skills/stonehenge-wiki/scripts/llm-wiki ask --wiki-root ./stonehenge-wiki "SQLite SELECT 命令是什么"
```

验证点：`opencode models` 可见到 runtime provider，`opencode run` 返回 `OK`。

注意：Skill 脚本 CLI 只调用 REST API，不直接调用 opencode，也不和 Python 解释器交互。opencode 配置用于统一本机 agent/provider/model 的命名和密钥来源；Stonehenge Wiki 后端通过 OpenAI-compatible REST endpoint 调用同一组能力。

开发验证：

```bash
python3 -m compileall -q work
PYTHONPATH=work python3 -m stonehenge_wiki.contract_checks
PYTHONPATH=work python3 -m unittest discover -s work/tests -q
./work/skills/stonehenge-wiki/scripts/llm-wiki health
```

## HTTP API

默认监听 `127.0.0.1:8765`。

- `GET /health`：健康检查和索引统计
- `GET /api/contract`：机器可读 REST API 契约，schema v2 包含 route、scope、query/body 字段 required/type/alias/enum 元数据、CLI 映射和 no-RAG 边界说明

`python3 -m stonehenge_wiki.contract_checks` 会静态校验 API contract 与 `server.py` 的 route/scope/query/body 字段、字段元数据，以及 CLI 能力映射是否一致；该检查已纳入 CI。
- `GET /`：浏览器控制台
- `GET /index`：文件、批注和持久化状态
- `GET /sources?include_missing=1`：来源注册表，包含 origin、hash、大小、状态和最后索引时间
- `GET /sources/detail?path=docs/03_学习材料/Knowledge-Notes.md`：来源详情，包含 metadata、脱敏抽取预览、版本、审核、风险和关联 wiki 区段
- `GET /sources/history?path=docs/03_学习材料/Knowledge-Notes.md`：来源版本历史，只记录路径、hash、大小和观测次数，不复制原始正文
- `GET /sources/risk`：来源风险扫描，检查提示注入、权限黑名单、密钥位置、危险代码、抽取失败和 TODO 风险
- `GET /sources/reviews?path=docs/00_inbox/risky.md`：来源审批/隔离历史
- `GET /audit?limit=50`：审计事件
- `GET /wiki/lint`：检查编译型 Markdown wiki
- `GET /wiki/sections?source_path=docs/04_常用命令/sqlite.md&limit=20`：查看编译后的 wiki 章节
- `GET /wiki/search?q=SQLite%20SELECT&limit=5`：搜索编译后的 wiki 章节
- `GET /reports/governance`：治理报告 JSON，包含来源状态、TODO 风险、审计阻断和任务历史
- `GET /files/output/...`：下载生成物，例如工作台演示文件
- `POST /ask`：单问，JSON body 示例 `{"id":"api-1","title":"统计 docx 文件数量","level":"简单"}`
- `POST /explain`：查看一次问题的检索证据、安全路由和匹配片段，JSON body 示例 `{"id":"trace-1","title":"SQLite SELECT 命令是什么","level":"中等"}`
- `POST /llm/test`：测试 LLM agent 配置或真实连接，JSON body 示例 `{"agent_name":"opencode","live":true}`
- `POST /groups/run`：运行题组，JSON body 示例 `{"groups":["group-1"]}`
- `POST /sources/import`：导入本地文件或公开 URL，JSON body 示例 `{"source":"https://example.com/page.html","title":"网页资料","category":"00_inbox"}`
- `POST /sources/status`：隔离或恢复来源，JSON body 示例 `{"path":"docs/00_inbox/risky.md","status":"quarantined","reason":"prompt injection review"}`
- `POST /slides/generate`：生成工作台演示文件，JSON body 示例 `{"topic":"企业知识库建设方案","slide_count":6}`
- `POST /reports/governance/export`：导出 Markdown 治理报告到 `output/reports/`
- `POST /reports/evaluation`：运行题组质量评估，JSON body 示例 `{"groups":["group-1"]}`
- `POST /reports/evaluation/export`：导出题组质量评估 Markdown/JSON 报告到 `output/reports/`
- `POST /reindex`：重建索引
- `POST /wiki/compile`：将 `docs/` 编译为 `wiki/` Markdown 知识层

导入接口会落盘到 `docs/<category>/`，支持 pdf、doc/docx、ppt/pptx、xls/xlsx、html、xml、md、代码和常见文本格式；私网、localhost、超大文件和 `Permission.json` 拒绝的路径会被阻断并记录审计。

如果设置了 `STONEHENGE_WIKI_API_TOKEN` 或 `STONEHENGE_WIKI_READ_TOKEN`，请求需携带 `X-STONEHENGE-WIKI-TOKEN`。`STONEHENGE_WIKI_READ_TOKEN` 可访问 `/index`、`/sources`、`/sources/detail`、`/sources/history`、`/sources/risk`、`/sources/reviews`、`/audit`、`/wiki/lint`、`/wiki/sections`、`/wiki/pages`、`/wiki/page`、`/wiki/search`、`/reports/governance`、`/files/...`、`/ask` 和 `/explain`；`STONEHENGE_WIKI_API_TOKEN` 是管理 token，可调用所有接口，包括导入、来源隔离/恢复、重建索引、编译 wiki、运行题组、工作台生成、导出治理报告和运行质量评估。控制台右上角的 `API token` 输入框会把 token 保存到浏览器本地存储并随请求发送。

## Skill 调用

仓库内置 Codex skill 位于：

```text
work/skills/stonehenge-wiki/
```

可直接调用 skill 下的脚本：

```bash
./work/skills/stonehenge-wiki/scripts/llm-wiki quick-start --wiki-root /path/to/stonehenge-wiki --question-id api-1 "统计 docx 文件数量"
```

如需安装到本机 Codex，可将 `work/skills/stonehenge-wiki` 复制到 `${CODEX_HOME:-$HOME/.codex}/skills/`。

## 输出约定

- 答案写入 `stonehenge-wiki/output/<group>-answer.md`
- 修复文件写入 `stonehenge-wiki/output/fixed/`
- 成功运行日志追加到 `result/output.md`
- 运行状态、索引、审计写入 `stonehenge-wiki/.state/wiki.sqlite`
- 来源注册表会记录 metadata-only 版本历史，包含路径、SHA-256、大小、首次/末次观测时间和观测次数
- 编译后的 wiki 章节索引写入 `wiki_sections` 表，用于 CLI/API 的 wiki 层搜索
- 治理报告和质量评估报告写入 `stonehenge-wiki/output/reports/`
- 高危命令统一返回 `{"error_msg":"高危命令，拒绝访问"}`
