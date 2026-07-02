# stonehenge-wiki 运行说明

## 环境

- 对外入口：`work/skills/stonehenge-wiki/bin/stonehenge-wiki`（Rust CLI）
- 构建依赖：Rust / Cargo
- 推荐依赖：`openpyxl`，用于更完整地读取 Excel 单元格批注并生成透视表/透视图文件
- 推荐外部程序：LibreOffice / `soffice`，用于 `.doc/.ppt/.xls` 老式 Office 文件转换、索引和修复

构建 skill CLI：

```bash
./work/scripts/build_skill_cli.sh
```

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

## CLI 入口

公开 CLI 位于 skill 目录下：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --help
```

CLI 是 REST API client，只通过 HTTP 调用 Stonehenge Wiki 服务，不启动本地服务、不执行项目源码。默认连接 `http://127.0.0.1:8765`；可通过 `--url`、`--token` 或 `STONEHENGE_WIKI_URL`、`STONEHENGE_WIKI_TOKEN` 指定服务地址和 token。

平台还提供 Linux / Windows 两个 Rust 入口用于对应平台打包：

```bash
cargo build --release --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --bin stonehenge-wiki-linux
cargo build --release --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --bin stonehenge-wiki-windows
```

处理 `stonehenge-wiki/question/` 下全部 `group-*.md`：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki
```

处理指定题组：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --group group-1
```

单问调试：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --ask "统计 docx 文件数量"
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --explain-ask "SQLite SELECT 命令是什么"
```

索引检查：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --dump-index
```

来源注册表：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-sources
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-sources --include-missing-sources
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --source-detail docs/03_学习材料/Knowledge-Notes.md
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-source-versions
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --source-history docs/03_学习材料/Knowledge-Notes.md
```

重建并持久化索引：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --reindex
```

导入知识源并自动重建索引：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --import-source ./docs/source.pdf --import-title "知识库评估材料" --import-category 03_学习材料
```

查看审计日志：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --audit-log --audit-limit 20
```

来源风险扫描：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --source-risk-report
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --set-source-status docs/00_inbox/risky.md --source-status quarantined --source-status-reason "prompt injection review"
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --set-source-status docs/00_inbox/risky.md --source-status active --source-status-reason "review complete"
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-source-reviews --source-review-path docs/00_inbox/risky.md
```

命中 `Permission.json.file.deny` 的来源会被策略自动隔离为 `quarantined`；隔离来源保留来源注册表、版本和风险记录，但不会进入问答、工作台生成或 compiled wiki 章节。

治理报告：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --governance-report
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --export-governance-report
```

质量评估报告：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --evaluation-report --group group-1
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --export-evaluation-report --group group-1
```

企业交付门禁：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --readiness-report --group group-demo
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --export-readiness-report --group group-demo
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --export-release-bundle --group group-demo
```

readiness report 会检查引擎运行时、`stonehenge-wiki` 目录结构、Rust CLI/skill 入口、文件类型支持、20-30 题题组契约、安全网关、compiled wiki、no-RAG 架构、来源隔离、修复输出目录、SQLite 审计、LLM 连接和 API token scope。release bundle 会打包报告、题组、答案和 compiled wiki，不打包原始 `docs/` 文件或 `.state/wiki.sqlite`。`manifest.json` 会记录生成者、artifact 数量、每个打包文件的 `size`/`sha256`，API 响应还会返回发布包自身的 `sha256`。

本地受保护运行可复制示例文件并填入真实 token：

```bash
cp stonehenge-wiki/.env.example stonehenge-wiki/.env
```

`stonehenge-wiki/.env` 会在 CLI、HTTP API、skill wrapper 和 readiness 入口启动时自动加载；shell 中已经设置的同名环境变量优先，不会被 `.env` 覆盖。`.env` 不应提交到 Git。

编译 Markdown wiki：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --compile-wiki
```

查看和搜索编译后的 wiki 章节：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-wiki-sections --wiki-section-limit 20
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --list-wiki-sections --wiki-section-source docs/04_常用命令/sqlite.md
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --search-wiki "SQLite SELECT" --wiki-section-limit 5
```

浏览器控制台的 `Wiki` 页面提供 compiled wiki 文章列表和同页预览，可直接点开 `wiki/index.md`、`wiki/sources/*.md`、`wiki/topics/*.md` 查看内容，不会回退读取原始 `docs/`。

检查 Markdown wiki：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --lint-wiki
```

REST API 服务启动后打开控制台：

```text
http://127.0.0.1:8765/
```

检查 REST API：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --url http://127.0.0.1:8765 --health
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --url http://127.0.0.1:8765 --api-contract
```

REST 自验证：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --health
```

## LLM Agent 与 opencode 配置

LLM 配置必须按 agent 隔离，不要把所有模型参数只堆在顶层 `llm` 字段里。`stonehenge-wiki/config.json` 的约定如下：

- `llm.agents.<name>`：一个可独立启停、独立 provider/model/env 的 agent 配置。
- `llm.default_agent`：默认问答、题组运行和工作台生成使用的 agent。
- `llm.category_agents`：按知识类别路由到指定 agent，例如 `03_学习材料` 使用 `opencode`。
- 顶层 `llm.provider/model/base_url/api_key_env/env_file` 保留为兼容字段，也会作为 agent 的 fallback。

当前默认 agent 是 `opencode`，它复用本机 Hermes 中已经可用的 DeepSeek API：

```json
{
  "llm": {
    "enabled": true,
    "default_agent": "opencode",
    "agents": {
      "opencode": {
        "enabled": true,
        "provider": "opencode-hermes-deepseek",
        "model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "env_file": "~/.hermes/.env",
        "timeout_seconds": 120,
        "max_context_chars": 16000,
        "max_tokens": 900,
        "temperature": 0.1
      }
    }
  }
}
```

如果本机还没有 opencode，或 opencode 没有 LLM provider 配置，直接使用 skill 脚本从本机 Hermes 配置中抽取已验证可用的 DeepSeek API：

```bash
./work/skills/stonehenge-wiki/scripts/configure_opencode_from_hermes.sh
```

脚本会执行三件事：

- 如果 `opencode` 不存在，则安装到 `~/.opencode/bin`，并复用 shell 中已有的 PATH 配置。
- 从 `~/.hermes/.env` 读取 `DEEPSEEK_API_KEY`，写入 `~/.config/opencode/hermes-deepseek.key`，权限固定为 `0600`。
- 写入 `~/.config/opencode/opencode.json`，配置 OpenAI-compatible provider `hermes-deepseek/deepseek-v4-pro`。

手工配置时也遵循同样约定。密钥文件只放在用户目录，不提交到仓库：

```bash
mkdir -p ~/.config/opencode
grep '^DEEPSEEK_API_KEY=' ~/.hermes/.env | cut -d= -f2- > ~/.config/opencode/hermes-deepseek.key
chmod 600 ~/.config/opencode/hermes-deepseek.key
```

`~/.config/opencode/opencode.json` 应使用 OpenAI-compatible provider，并通过 `{file:...}` 引用密钥文件：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "hermes-deepseek/deepseek-v4-pro",
  "small_model": "hermes-deepseek/deepseek-v4-pro",
  "provider": {
    "hermes-deepseek": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Hermes DeepSeek",
      "options": {
        "baseURL": "https://api.deepseek.com/v1",
        "apiKey": "{file:~/.config/opencode/hermes-deepseek.key}"
      },
      "models": {
        "deepseek-v4-pro": {
          "name": "DeepSeek V4 Pro",
          "limit": {
            "context": 16000,
            "output": 900
          }
        }
      }
    }
  },
  "enabled_providers": ["hermes-deepseek"]
}
```

验证顺序：

```bash
opencode --version
opencode models hermes-deepseek
opencode run -m hermes-deepseek/deepseek-v4-pro --pure --format json "只回复 OK"
python3 -m json.tool stonehenge-wiki/config.json >/dev/null
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --url http://127.0.0.1:8765 --health
curl -s http://127.0.0.1:8765/llm/config | python3 -m json.tool
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --test-llm-agent opencode --test-llm-live
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --ask "SQLite SELECT 命令是什么"
```

本机 2026-07-02 验证结果：opencode `1.17.13` 能列出 `hermes-deepseek/deepseek-v4-pro`，`opencode run` 最小请求返回 `OK`，Stonehenge Wiki `--test-llm-agent opencode --test-llm-live` 返回 `reply_preview: OK`。

注意：Stonehenge Wiki 的 Rust CLI 只调用 REST API，不直接调用 opencode，也不和 Python 解释器交互。opencode 配置用于统一本机 agent/provider/model 的命名和密钥来源；Stonehenge Wiki 后端通过 OpenAI-compatible REST endpoint 调用同一组能力。

开发验证：

```bash
python3 -m compileall -q work
PYTHONPATH=work python3 -m stonehenge_wiki.contract_checks
PYTHONPATH=work python3 -m unittest discover -s work/tests -q
cargo fmt --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --check
cargo test --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml
./work/scripts/build_skill_cli.sh
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --health
```

## HTTP API

默认监听 `127.0.0.1:8765`。

- `GET /health`：健康检查和索引统计
- `GET /api/contract`：机器可读 REST API 契约，schema v2 包含 route、scope、query/body 字段 required/type/alias/enum 元数据、CLI 映射和 no-RAG 边界说明

`python3 -m stonehenge_wiki.contract_checks` 会静态校验 API contract 与 `server.py` 的 route/scope/query/body 字段、字段元数据、Rust CLI flag/path 是否一致；该检查已纳入 CI。
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

可直接调用 skill 下的 Rust CLI：

```bash
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --group group-1
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
