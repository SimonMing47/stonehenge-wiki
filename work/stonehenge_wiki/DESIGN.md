# Stonehenge Wiki 详细设计文档（企业知识工作台）

**版本**：v1.1
**更新日期**：2026-07-02
**适用范围**：`stonehenge-wiki` 项目内 `work/stonehenge_wiki` 平台

## 1. 目标与约束

### 1.1 目标

- 提供可复用的企业知识库平台，支持以下核心能力：
  - 知识源接入（本地文件 + 公开 URL）
  - 自动索引与持久化
  - 编译型知识层（Compiled Wiki）构建与检索
  - 高危命令/敏感动作审计与阻断
  - 问答、解释、题组运行
  - 受控内容修复输出
  - 治理、就绪度、质量评估与发布包生成
  - 控制台、REST API、Rust CLI、skill 三端统一入口
- 提供可展示的工作台页面：问答、知识库、原始源、LLM 配置、治理、审计、演示稿生成入口。

### 1.2 非目标

- 不依赖向量数据库（RAG）
- 不托管大规模外部文档系统
- 不引入云端独立检索索引服务

### 1.3 关键约束

- **安全优先**：命令与文件动作必须经过白名单/黑名单策略与统一审计。
- **统一口径**：CLI、skill、HTTP API、Web Console 共享同一平台服务层。
- **可治理**：所有关键动作有来源、时间、操作者、风险等级和证据留痕。
- **可回放**：重要事件与版本信息可回溯，不依赖外部状态。

---

## 2. 总体架构

```text
客户端
  ├─ Web Console (localhost 控制台)
  ├─ Rust CLI REST Client (work/skills/stonehenge-wiki/cli)
  └─ Skill Wrapper (work/skills/stonehenge-wiki)
        │
        ▼
Stonehenge Wiki REST API (work/stonehenge_wiki/server.py)
        │
        ▼
Stonehenge Wiki Platform (work/stonehenge_wiki/platform.py)
        │
        ├─ 配置与环境（config.py）
        ├─ 安全与权限（Permission.json / security.py）
        ├─ 索引与持久化（store.py）
        ├─ 导入器（importer.py）
        ├─ 提取器（extractors.py）
        ├─ 编译层（wiki_compiler.py）
        ├─ 章节索引（wiki_sections.py）
        ├─ 问答/解释（answerer.py + llm.py）
        ├─ 修复与执行（repair.py / execution.py）
        ├─ 报告（reports.py / evaluation.py / readiness.py）
        ├─ 风险扫描（source_risk.py）
        ├─ Office 兼容层（office_bridge.py）
        └─ HTTP 端点（server.py）
             └─ 文件服务 / 输出下载（/files/...）
```

### 2.1 分层说明

- **入口层**：Web / HTTP / Skill / Rust CLI 统一通过 REST API 触发平台动作。
- **服务层**：`StonehengeWikiPlatform` 承载业务流转、校验与编排。
- **持久层**：SQLite（`.state/wiki.sqlite`）保存索引快照、审计、任务记录、来源状态。
- **知识层**：`docs/` 作为原始源，`wiki/` 作为编译后的可检索知识层。
- **展示层**：`web/index.html + web/app.js + web/assets/*` 提供可见控制台。

---

## 3. 数据与文件结构

### 3.1 目录规范（`stonehenge-wiki/`）

- `docs/`：原始知识源（PDF/HTML/MD/代码/Office）
- `wiki/`：编译后的知识库产物（`index.md`、`sources/*.md`、`topics/*.md`、`log.md`）
- `question/`：题组定义（如 `group-*.md`）
- `output/`：答案、评估报告、生成物（含演示稿文件）
- `.state/wiki.sqlite`：系统状态、索引、审计
- `Permission.json`：安全与高危规则
- `config.json`：运行时开关、端口、LLM 配置、鉴权变量名等
- `.env`：运行时凭证注入（可选）

### 3.2 核心表与数据流

- `source_registry`：来源级索引（路径、状态、hash、元信息、风险标签）
- `source_versions`：来源元数据快照历史（仅 metadata，非原文）
- `index_entries`：已索引文件与注释元信息
- `wiki_sections`：编译后章节索引（问答与 search 的检索单位）
- `comments`：解析到的 TODO/批注注解
- `audit_events`：所有阻断、导入、运行、配置变更事件
- `job_runs`：题组/评估/治理/导出等任务运行记录

---

## 4. 关键链路设计

### 4.1 知识导入链路

```text
用户输入（file path / URL）
   │
   ├─> CLI / Web / API
   ├─> 安全校验（私网阻断、后缀白名单、大小阈值、Permission 命中）
   ├─> 落盘到 docs/<category>/  
   ├─> 元数据写入 source_registry
   ├─> 触发索引重建（可选）
   ├─> wiki 编译与问题摘要更新
   └─> 审计事件落库
```

### 4.2 问答链路（非 RAG）

```text
问题输入
   ├─> 输入标准化与题组上下文封装
   ├─> LLM 可用性检测 + 安全开关
   ├─> 在 wiki_sections 上检索（知识层，而非原始源）
   ├─> 证据路由构建（命中文件 + 行号 / 片段 + 风险标签）
   ├─> 答案生成并返回 JSON schema
   └─> 结果记录到任务运行与审计
```

LLM 通过 `config.json` 的 `llm.agents` 独立配置。当前默认 `opencode` agent 使用本机 Hermes 的 `DEEPSEEK_API_KEY`，provider 标记为 `opencode-hermes-deepseek`，运行时通过 OpenAI-compatible REST endpoint 调用，不要求 Rust CLI 直接调用 opencode 或 Python。

`POST /llm/test` 提供 agent 级诊断：默认检查启用状态、provider/model/base_url、环境变量和密钥可见性；`live=true` 时发起最小 chat completions 探活。诊断结果不返回密钥值，并写入 `llm.test` 审计事件。

### 4.3 explain 链路

在返回回答的同时提供：
- 命中章节
- 来源路径与来源状态
- 安全判断（是否通过、命中拦截原因）
- 检索路径（routing）
- 证据片段摘要

### 4.4 修复/执行链路

- 仅对被允许的安全命令/代码片段提供隔离执行
- Python/脚本执行走最小权限、时间限制、错误标准化输出
- 所有高危操作先验阻断（拒绝时返回统一错误对象）
- 修复文件输出落 `output/fixed/`，并记录版本/审计

### 4.5 演示物生成（工作台）

- 前端“工作台”页面提供主题输入与页数配置。
- 后端通过 `/slides/generate` 生成文件产物（默认输出 `.pptx` 格式）。
- 返回下载链接到文件服务 `/files/output/...`。
- UI 上不展示 “PPT” 文案，统一改为“工作台/生成演示稿/下载文件”。

### 4.6 监控与治理

- 运行时 `health` 暴露文件数/审计数/LLM 状态/鉴权状态
- `audit` 提供最近事件时间线
- `governance` 汇总来源状态、风险、TODO、阻断、任务历史
- `readiness` 输出企业交付门禁（fail/warn/ok + 严重性）
- `evaluation` 输出题组质量指标与风险分布，用于 CI 或交付前校验
- `release` 输出 metadata-only bundle，manifest 记录生成者、artifact 清单、size/sha256，不打包原始 `docs/` 或 `.state/wiki.sqlite`

---

## 5. 安全与权限模型

### 5.1 双令牌模型

- `STONEHENGE_WIKI_API_TOKEN`：管理员操作（导入、重建、编译、题组执行、生成输出、导出）
- `STONEHENGE_WIKI_READ_TOKEN`：只读操作（查看索引、审计、问答、治理结果）
- 无 token 时按配置支持公开读写（默认不推荐）
- API 均以 `X-STONEHENGE-WIKI-TOKEN` 头传入

### 5.2 风险网关

- 基于 `Permission.json`：
  - `command.deny`：危险命令阻断
  - `file.deny`：敏感路径禁止读写
  - `dir.deny`：目录级黑名单
- 私网/localhost URL、未知扩展、超大文件、不可解析内容都可触发阻断
- 命中风险必须可追溯到 `audit_events`

### 5.3 来源治理

- `active / quarantined` 双状态
- 隔离来源保留元数据与审计，但不参与问答、搜索、演示生成的知识上下文

---

## 6. 接口与能力映射

### 6.1 CLI 能力与服务能力映射

- Rust CLI 是 REST API client，只负责把命令行参数映射为 HTTP 请求。
- `--url` / `--token` 或 `STONEHENGE_WIKI_URL` / `STONEHENGE_WIKI_TOKEN` 控制目标服务和鉴权。
- `--api-contract` 对应 `GET /api/contract`，用于 skill、CI、前端和第三方调用方读取统一 route/scope/query/body 字段元数据/CLI 契约。
- `--import-source` / `--compile-wiki` / `--reindex` / `--lint-wiki`
- `--ask` / `--explain-ask` / `--question` / `--group`
- `--generate-brief` / `--generate-ppt`（工作台产物，后者保留为兼容别名）
- `--audit-log` / `--list-sources` / `--source-risk-report`
- `--governance-report` / `--evaluation-report` / `--readiness-report` / `--export-*`

### 6.2 HTTP 入口（当前实现）

健康与索引：
- `GET /health`, `GET /api/contract`, `GET /index`, `GET /audit`

知识与来源：
- `GET /sources`, `GET /sources/history`, `GET /sources/risk`, `GET /sources/reviews`
- `GET /sources/detail`
- `POST /sources/import`, `POST /sources/status`

问答：
- `POST /ask`, `POST /explain`, `POST /groups/run`

编辑与治理：
- `POST /reindex`, `POST /wiki/compile`, `GET /wiki/lint`
- `GET /wiki/sections`, `GET /wiki/pages`, `GET /wiki/page`, `GET /wiki/search`
- `GET /reports/governance`, `POST /reports/governance/export`
- `GET /reports/readiness`, `POST /reports/readiness`, `POST /reports/readiness/export`
- `POST /reports/evaluation`, `POST /reports/evaluation/export`
- `POST /reports/release/export`
- `GET /llm/config`, `POST /llm/config`
- `POST /llm/test`

工作台（演示物）：
- `POST /slides/generate`

文件服务：
- `GET /files/*`（产物下载）

---

## 7. Web 控制台设计

### 7.1 页面与路由

- `ask`：单问、组测与解释
- `wiki`：知识源列表 + 编译库预览 + 章节搜索
- `studio`：演示物工作台
- `sources`：原始源列表、导入、注释展示
- `agents`：LLM 配置与分类映射
- `governance`：治理与就绪结果展示
- `audit`：安全与操作事件时间线

### 7.2 关键交互行为

- 页面初始化后触发 `refreshAll` 聚合请求
- 所有操作统一走 `fetch` 封装，携带本地缓存 token
- 响应失败时降级显示 `status.failed` 并写入错误说明
- 支持中文/英文文案切换

### 7.3 文案与品牌约定（已更新）

- 品牌标题统一为 `Stonehenge Wiki`
- 工作台页签改为 `工作台`（中文）/`Workbench`（英文）
- 所有页面显示不再直接出现 `PPT` 字样（下载与生成动作改为“下载文件/生成演示稿”）

---

## 8. 可交付与部署

- 启动：由部署层启动 Stonehenge Wiki REST API，默认监听 `127.0.0.1:8765`
- 守护运行：外部用 `screen/systemd/launchd` 等方式维持进程
- 健康检查：`curl http://127.0.0.1:8765/health`
- 可回归验证：
  - `python3 -m compileall -q work`
  - `PYTHONPATH=work python3 -m stonehenge_wiki.contract_checks`
  - `PYTHONPATH=work python3 -m unittest discover -s work/tests -q`
  - `cargo fmt --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --check`
  - `cargo test --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml`
  - `./work/skills/stonehenge-wiki/scripts/build_skill_cli.sh`
  - `./work/skills/stonehenge-wiki/bin/stonehenge-wiki --health`

---

## 9. 可扩展点与演进建议

1. **多租户 token 域**：按 tenant 细分审计与配额
2. **任务队列化**：将重索引/编译/导出移动到后台队列，减少 UI 阻塞
3. **知识版本比对**：对编译后的 markdown 增加版本 hash 追踪与回滚
4. **风险规则市场化**：将 `Permission.json` 拆分为规则包，可按业务加载
5. **工作台产物类型扩展**：在不改动现有逻辑前提下支持 Markdown 报告或 HTML deck

---

## 10. 已知边界与注意事项

- `HEAD` 在当前服务端口返回 `501`（标准 HTTP 行为，非功能故障）
- Office 旧格式依赖外部转换能力（未安装 `soffice` 时会降级读取策略）
- 演示物文件仍按历史约定使用 `.pptx` 后缀，属于产物格式属性，不代表页面文案要展示对应缩写
- 文件系统与 token 配置由 `.env` 和环境变量共同控制，建议仅在受控环境下设置高权限 token

---

## 11. 里程碑交付清单

- [x] no-RAG 架构落地（compiled wiki 为主）
- [x] Rust REST CLI/skill/API/console 统一平台层
- [x] 来源治理与隔离机制
- [x] Raw 来源详情：metadata、脱敏抽取预览、版本、审核、风险和 wiki 区段
- [x] 审计与治理报告
- [x] 就绪度门禁与评估报告
- [x] opencode 独立 LLM agent 配置与 Hermes DeepSeek 复用
- [x] LLM agent 连接诊断 API、CLI 与 Agents 页面入口
- [x] Web 页面“工作台”与“Stonehenge Wiki”命名统一

---

## 12. 三人协作分工

项目按三条 owner 线维护，详细项目级计划见仓库根目录 `DESIGN.md`。

### 12.1 平台/API/安全 owner

负责 `platform.py`、`server.py`、`store.py`、`security.py`、`source_risk.py`、`importer.py`、`config.py` 和 `Permission.json`。该 owner 对 REST API 契约、token scope、SQLite schema、来源隔离、安全审计和 readiness 关键门禁负责。

### 12.2 Web Console/产品体验 owner

负责 `web/index.html`、`web/app.js`、`web/styles.css`、favicon 和页面信息架构。该 owner 对 Ask、Wiki、Workbench、Raw、Agents、Governance、Audit 的可见状态、响应式布局、树状知识库、知识图谱和错误提示负责。

### 12.3 CLI/Skill/质量与发布 owner

负责 `work/skills/stonehenge-wiki/`、Rust CLI、`INSTRUCTION.md`、顶层 `DESIGN.md`、测试矩阵、release bundle 和 GitHub 发布。该 owner 确保公开 CLI 只调用 REST API，不与 Python 本地实现交互。

### 12.4 协作门禁

- API、schema、安全、鉴权、输出格式变更必须跨 owner review。
- UI 新能力必须有 API 契约和测试覆盖。
- CLI 参数变更必须同步 skill 文档、运行说明和 smoke test。
- 每个里程碑必须保留验证命令、截图或报告路径。

---

## 13. 未来里程碑摘要

| 里程碑 | 目标 | 主要交付 |
| --- | --- | --- |
| M1 项目工程化 | 让 3 人稳定协作 | CI、CONTRIBUTING、CHANGELOG、PR/Issue 模板、API contract |
| M2 知识运营闭环 | 从导入到治理、预览、编译、问答闭环 | 来源详情、版本历史、原始源预览、图谱边类型 |
| M3 安全与治理增强 | 企业可验收安全能力 | 风险分级、source review、token scope、审计导出 |
| M4 工作台成熟化 | 日常可用的问答和生成工作台 | 历史记录、证据展开、LLM 连接测试、配置回滚 |
| M5 发布与生产化 | 可交付版本和运维手册 | CLI release artifact、部署手册、备份恢复、性能基线 |

---

该文档与现有实现一一对应，后续如有字段命名、路由变更、owner 调整或里程碑变化，请同步更新本文件“接口与能力映射”“安全与权限”“三人协作分工”章节。
