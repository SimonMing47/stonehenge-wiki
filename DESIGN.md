# Stonehenge Wiki 项目级设计文档

**版本**：v1.1
**更新日期**：2026-07-02
**目标读者**：产品负责人、后端/平台工程师、前端工程师、测试/交付工程师、Codex skill 维护者
**项目阶段**：从可运行原型升级为 3 人协作的成熟项目

---

## 1. 项目定位

Stonehenge Wiki 是一个基于 LLM Wiki 理念的企业知识工作台。它不把知识库设计成“原文切片 + 向量召回 + 直接生成”的 RAG 系统，而是采用三层结构：

1. `docs/`：原始知识源，保存 PDF、网页、代码、Office 文档、Markdown、XML、CSV/XLSX 等资料。
2. `wiki/`：编译后的 Markdown 知识层，保存可维护、可审计、可预览、可搜索的 wiki 页面。
3. `AGENTS.md` / `Permission.json` / `config.json`：维护契约、安全规则和运行配置。

系统面向两类场景：

- **知识运营**：导入资料、组织分类、查看原始源、生成 compiled wiki、在同页预览文章、查看知识树和知识图谱关系。
- **企业交付**：问答、解释、来源审计、风险隔离、报告导出、演示物工作台、题组评估、readiness gate、release bundle。

项目必须同时提供：

- Web Console：面向用户的可视化工作台。
- REST API：所有能力的统一服务入口。
- Rust CLI：面向 skill、CI、Linux/Windows 终端的 REST API client。
- Codex Skill：面向 Codex 调用的能力封装。

---

## 2. 设计原则

### 2.1 不引入 RAG

系统不引入向量数据库，不保存原文切片表，不把召回面设计为黑盒 embedding 检索。检索对象是 compiled wiki 的章节索引 `wiki_sections`，核心目标是让知识先被整理为可维护页面，再被问答、解释和生成链路使用。

### 2.2 REST 是统一边界

公开 CLI 只调用 Stonehenge Wiki REST API。Rust CLI 不启动服务，不导入 Python，不 fork 本地脚本，不读取项目内部模块。所有入口都应该走同一套 HTTP 能力和安全规则，避免 CLI、Web、skill 出现行为分叉。

### 2.3 安全前置

任何导入、问答、修复、代码执行、文件下载、来源状态变更、报告导出都要经过权限判断和审计记录。高危命令、黑名单文件、prompt injection、私网 URL、超大文件、敏感路径都必须被阻断或隔离。

### 2.4 可治理、可回放

核心状态进入 SQLite：

- 文件索引
- 批注/TODO
- 来源注册表
- 来源版本 metadata
- wiki 章节索引
- 审计事件
- 任务运行记录

release bundle 不打包原始 `docs/` 和 `.state/wiki.sqlite`，只打包报告、题组、答案、配置契约和 compiled wiki，降低敏感资料二次扩散风险。

### 2.5 前端是控制面

Web Console 不只是演示页，而是知识运营控制面。每个侧边栏入口独立承载页面；页面要能反映真实后端状态，包括 token scope、LLM 状态、知识模式、风险数量、审计事件、来源状态和 readiness gate。

---

## 3. 产品能力范围

### 3.1 当前已具备能力

- 多格式知识源读取：PDF、HTML、MD、XML、代码、CSV/XLSX、DOCX/PPTX 等。
- 可选 Office 旧格式转换：通过 LibreOffice/`soffice` 转换 `.doc/.ppt/.xls`。
- 原始源注册表：记录来源、hash、大小、状态、缺失状态和版本 metadata。
- 原始源详情：同页查看来源 metadata、脱敏抽取预览、版本、审核、风险和关联 wiki 区段。
- 来源隔离：`active/quarantined/missing` 状态，隔离来源不进入问答和 compiled wiki。
- compiled wiki：生成 `wiki/index.md`、`wiki/sources/*.md`、`wiki/topics/*.md`、`wiki/log.md`。
- wiki 章节索引：以 compiled wiki 章节为搜索和问答证据面。
- 问答与解释：支持严格 JSON 答案、路由解释、证据片段、安全判断。
- 安全网关：高危命令、敏感路径、危险代码、私网 URL 和 prompt injection 阻断。
- 修复输出：对 TODO/批注驱动的安全修复输出到 `output/fixed/`。
- LLM 配置：支持 opencode 独立 agent、本地 Hermes/DeepSeek 凭证复用和分类路由。
- LLM 诊断：支持按 agent 检查配置完整性，并可触发最小 live 探活。
- 工作台生成：生成演示物文件，页面文案统一为“工作台/生成演示稿/下载文件”。
- 治理报告：来源状态、TODO 风险、阻断审计、任务历史汇总。
- readiness report：企业交付门禁。
- evaluation report：题组质量评估。
- release bundle：交付归档。
- Web Console：Ask、Wiki、Workbench、Raw、Agents、Governance、Audit。
- Rust REST CLI：Linux/Windows 入口和 skill 内二进制构建脚本。
- 机器可读 API contract：`GET /api/contract` 和 Rust CLI `--api-contract` 暴露 route、scope、CLI 映射与 no-RAG 边界。
- Favicon/品牌：Stonehenge Wiki + `SW` 页签图标。

### 3.2 成熟项目需要补齐能力

- 后台任务模型：导入、重索引、编译、导出不应长时间阻塞前端。
- 多用户/多租户 token scope：至少支持 tenant、role、read/admin 三层。
- 文档版本差异：对 compiled wiki 页面维护 hash、变更摘要和回滚点。
- 知识图谱增强：从共享来源、内链、主题、实体提取生成更清晰的关系边。
- Web Console 交互增强：来源详情、原文预览、版本历史 diff、任务进度、失败重试。
- 测试矩阵增强：Rust CLI 行为测试、HTTP token scope 测试、前端端到端 smoke、Office 样例回归。
- 发布工程：CI、版本号、CHANGELOG、release artifact、跨平台 CLI 产物。
- 运维文档：部署、备份、恢复、日志、故障排查、安全配置模板。

---

## 4. 总体架构

```text
用户 / Codex / CI
  │
  ├─ Web Console
  ├─ Rust CLI REST Client
  └─ Codex Skill
       │
       ▼
Stonehenge Wiki REST API
       │
       ├─ Auth + Token Scope
       ├─ Audit Middleware
       └─ Request Validation
       │
       ▼
StonehengeWikiPlatform
       │
       ├─ Config Layer
       ├─ Permission Guard
       ├─ Importer
       ├─ Extractors
       ├─ Source Registry
       ├─ Wiki Compiler
       ├─ Wiki Sections
       ├─ Answer / Explain
       ├─ LLM Router
       ├─ Repair / Execution
       ├─ Reports / Evaluation / Readiness
       └─ Presentation Generator
       │
       ▼
SQLite Store + File Outputs
       │
       ├─ .state/wiki.sqlite
       ├─ wiki/
       ├─ output/fixed/
       ├─ output/reports/
       ├─ output/presentations/
       └─ output/releases/
```

### 4.1 模块边界

| 层级 | 模块 | 职责 | 禁止事项 |
| --- | --- | --- | --- |
| Web | `work/stonehenge_wiki/web/*` | 展示、表单、状态、交互 | 不直接读本地文件，不绕过 API |
| REST | `server.py` | HTTP 路由、鉴权、JSON/文件响应 | 不复制业务逻辑 |
| Platform | `platform.py` | 编排导入、索引、问答、报告、生成 | 不直接写 UI 状态 |
| Store | `store.py` | SQLite 持久化 | 不保存原始正文副本 |
| Security | `security.py`, `source_risk.py` | 权限、风险、隔离、审计证据 | 不做静默放行 |
| Wiki | `wiki_compiler.py`, `wiki_sections.py` | compiled wiki 生成和章节索引 | 不退回向量库/RAG |
| CLI | `work/skills/stonehenge-wiki/cli` | REST API client | 不调用 Python/本地项目代码 |
| Skill | `work/skills/stonehenge-wiki` | Codex 使用说明和 CLI 包装 | 不实现另一套能力 |

### 4.2 数据流

#### 知识导入

```text
Input path / public URL
  -> API / CLI / Web
  -> PermissionGuard + SSRF check + extension check
  -> docs/<category>/ normalized copy
  -> source_registry + source_versions
  -> index rebuild
  -> optional wiki compile
  -> audit_events
```

#### 编译知识层

```text
docs/
  -> extract text + metadata + comments
  -> sanitize secrets and prompt injection
  -> wiki/sources/*.md
  -> wiki/topics/*.md
  -> wiki/index.md + wiki/log.md
  -> wiki_sections table
```

#### 问答

```text
Question
  -> standard question schema
  -> PermissionGuard intent check
  -> search wiki_sections
  -> build evidence route
  -> optional LLM answer
  -> strict JSON response
  -> job_runs + audit_events
```

#### 来源隔离

```text
source risk detected
  -> source_registry.status = quarantined
  -> source_reviews append
  -> excluded from wiki compile and answer context
  -> visible in Raw/Governance/Audit
```

---

## 5. 数据模型与契约

### 5.1 文件目录契约

```text
stonehenge-wiki/
  docs/
  wiki/
  question/
  output/
    fixed/
    presentations/
    reports/
    releases/
  Permission.json
  AGENTS.md
  config.json
  .env.example
work/
  main.py
  stonehenge_wiki/
  skills/stonehenge-wiki/
result/
  output.md
```

### 5.2 SQLite 核心表

| 表 | 内容 | 生命周期 |
| --- | --- | --- |
| `index_entries` | 文件路径、类型、大小、hash、抽取摘要 | 可重建 |
| `comments` | TODO/批注、负责人、截止日期、来源位置 | 可重建 |
| `source_registry` | 来源状态、origin、hash、大小、风险标签 | 持久治理状态 |
| `source_versions` | metadata-only 来源版本历史 | 持久审计状态 |
| `wiki_sections` | compiled wiki 章节索引 | 可重建 |
| `audit_events` | 阻断、导入、运行、导出、配置变更 | 持久审计 |
| `job_runs` | 题组、评估、导出任务结果 | 持久追踪 |

### 5.3 API 兼容契约

- 成功响应使用 JSON object，不返回裸字符串。
- API contract 统一由 `GET /api/contract` 暴露，包含 route、scope、query/body 概要、CLI 映射和 no-RAG 架构边界。
- 文件下载统一走 `/files/output/...`。
- 高危动作统一返回 `{"error_msg":"高危命令，拒绝访问"}`。
- read token 只允许读索引、来源、审计、wiki、报告、问答解释和文件下载。
- admin token 才允许导入、隔离/恢复、重建、编译、题组运行、生成、导出。

### 5.4 CLI 契约

Rust CLI 的职责是把命令行参数翻译为 HTTP 请求：

- 默认服务地址：`http://127.0.0.1:8765`
- 服务地址：`--url` / `STONEHENGE_WIKI_URL`
- token：`--token` / `STONEHENGE_WIKI_TOKEN`
- token header：`X-STONEHENGE-WIKI-TOKEN`
- 禁止：导入 Python、调用 `work/main.py`、读取内部模块、绕过 REST API。

---

## 6. Web Console 信息架构

### 6.1 页面

| 页面 | 目标 | 核心组件 |
| --- | --- | --- |
| Ask | 问答、解释、题组运行 | question textarea、level、answer output、group runner |
| Wiki | compiled wiki 阅读 | 知识树、同页预览、知识图谱、章节搜索 |
| Workbench | 生成演示物 | topic、slide count、artifact output |
| Raw | 原始源治理 | source import、source list、comments、source details |
| Agents | LLM 配置 | agent list、category map、provider/model/env |
| Governance | 治理与交付 | governance report、readiness gates、source risk review |
| Audit | 审计事件 | timeline、severity、actor、evidence |

### 6.2 交互要求

- 每个侧边栏入口是独立页面，不把多个页面堆在同一屏。
- Wiki 页面要同时支持树状列表和同页预览，点击文章不跳出页面。
- Raw 页面要能查看原始源状态、来源路径、版本、风险和注释。
- Governance 页面要能一眼看出 pass/warn/fail 和 release readiness。
- Agents 页面保存前后都要明确状态，不允许静默失败。
- 页面不显示旧品牌名，统一品牌为 `Stonehenge Wiki`。
- 页面上生成入口称为“工作台”，避免直接展示 “PPT” 文案。

### 6.3 可访问性与视觉标准

- 主要按钮有明确 label，危险动作需要可见状态。
- 文本不能溢出卡片，长模型名、文件名、路径要可换行但不能穿模。
- 移动端侧边栏横向滚动，内容页面单列。
- favicon、侧边栏 mark、页面标题保持统一品牌识别。

---

## 7. 安全设计

### 7.1 威胁模型

| 威胁 | 例子 | 防护 |
| --- | --- | --- |
| 高危命令 | 删除文件、读取系统密码 | `Permission.json.command.deny` + intent check |
| 敏感文件泄露 | `.env`、keychain、黑名单路径 | `file.deny` + source quarantine |
| SSRF | 导入 localhost/private URL | URL host/IP 检查 |
| Prompt injection | 文档内“忽略规则” | source risk scanner + compiled wiki sanitize |
| 原文扩散 | release bundle 打包原始 docs | release bundle 排除 docs 和 sqlite |
| 权限绕过 | read token 调 admin API | token scope enforcement |
| CLI 绕过服务 | CLI 直接调内部脚本 | Rust CLI REST-only policy |

### 7.2 审计事件

必须记录：

- 导入成功/失败
- 来源隔离/恢复
- 高危命令阻断
- 权限拒绝
- 问答/解释运行
- 题组运行
- wiki compile/lint
- 报告导出
- release bundle 导出
- LLM 配置保存

### 7.3 安全验收

每个里程碑至少跑：

- 高危命令题组
- 黑名单文件导入
- prompt injection 文档
- read/admin token scope
- release bundle 内容检查
- quarantined 来源排除检查

---

## 8. 三人团队分工

团队按职责分成三条线，既能并行，又能互相 review。

### 8.1 角色 A：平台/API/安全负责人

**职责范围**

- `work/stonehenge_wiki/platform.py`
- `server.py`
- `store.py`
- `security.py`
- `source_risk.py`
- `importer.py`
- `config.py`
- `Permission.json` 契约
- token scope 和审计模型

**核心交付**

- REST API 稳定性
- SQLite schema 演进
- 导入/隔离/版本治理
- 安全网关和审计
- readiness/evaluation 关键门禁

**验收指标**

- API smoke 全绿
- token scope 测试全绿
- 高危命令和敏感文件阻断全绿
- schema 变更有迁移或兼容策略

### 8.2 角色 B：Web Console/产品体验负责人

**职责范围**

- `work/stonehenge_wiki/web/index.html`
- `web/app.js`
- `web/styles.css`
- favicon/品牌资源
- 页面信息架构和交互状态

**核心交付**

- Ask/Wiki/Workbench/Raw/Agents/Governance/Audit 页面体验
- 知识树与知识图谱交互
- 原始源预览、来源详情、风险提示
- 响应式布局与中英文文案
- 可见错误状态和 loading 状态

**验收指标**

- 桌面和移动视口不穿模
- 页面无旧品牌名残留
- 页面无直接 “PPT” 可见文案
- 所有操作有成功/失败状态
- 浏览器 smoke 和截图验收通过

### 8.3 角色 C：CLI/Skill/质量与发布负责人

**职责范围**

- `work/skills/stonehenge-wiki/`
- Rust CLI
- `INSTRUCTION.md`
- `DESIGN.md`
- `stonehenge-wiki/README.md`
- tests、release bundle、CI、版本发布

**核心交付**

- Rust CLI Linux/Windows 包装
- Codex skill 使用说明
- 测试矩阵和回归脚本
- 发布包、CHANGELOG、里程碑文档
- 交付验收和 GitHub main 推送

**验收指标**

- Rust CLI 不依赖 Python，不绕过 REST
- `cargo test` 通过
- smoke tests 通过
- release bundle 不含敏感原始源
- 每个里程碑有清晰版本号和验收记录

### 8.4 协作规则

- A 改 API 时必须通知 B/C 更新前端调用和 CLI 映射。
- B 新增 UI 操作时必须确认 A 提供 API，C 补测试。
- C 调整 CLI 参数时必须确认 A API 能力和 B 文案一致。
- 任一人改安全、鉴权、输出 schema、SQLite schema，必须由另外两人 review。
- `main` 始终可运行；大改走 feature branch，合并前跑完整验证。

---

## 9. 里程碑规划

### M0：当前基线固化（已完成）

**目标**：把已有原型稳定为可交付基线。

**已完成**

- Stonehenge Wiki 品牌统一。
- `stonehenge-wiki/` 数据目录和 `work/stonehenge_wiki/` 包名统一。
- Rust CLI 移到 skill 下，并改为 REST-only。
- Web 页面分为独立路由。
- Wiki 页面支持知识树、同页预览和知识图谱容器。
- Raw 页面可查看来源数据。
- Favicon 添加到页签。
- GitHub 仓库已推送到 `SimonMing47/stonehenge-wiki`。

**验收命令**

```bash
python3 -m compileall -q work
PYTHONPATH=work python3 -m stonehenge_wiki.contract_checks
PYTHONPATH=work python3 -m unittest discover -s work/tests -q
cargo fmt --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --check
cargo test --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml
./work/skills/stonehenge-wiki/scripts/build_skill_cli.sh
./work/skills/stonehenge-wiki/bin/stonehenge-wiki --health
```

### M1：项目工程化（第 1 周）

**目标**：让 3 人能稳定协作，不互相踩边界。

**范围**

- 统一 `CONTRIBUTING.md`、`CHANGELOG.md`、版本策略。
- 增加 GitHub Actions：Python smoke、API contract、Rust fmt/test、skill build。
- 建立 issue/PR 模板。
- 梳理 API contract 表，形成兼容规则。
- 清理所有过期文档命令。

**分工**

- A：API contract、token scope 文档、schema 兼容策略。
- B：UI 状态矩阵和页面验收截图基线。
- C：CI、PR 模板、CHANGELOG、发布流程。

**验收**

- PR 必须自动跑 Python + Rust checks。
- README/INSTRUCTION/DESIGN 中无过期命令。
- 本地一键验证命令可复制运行。

### M2：知识运营闭环（第 2 周）

**目标**：让资料从导入到治理、预览、编译、问答形成闭环。

**范围**

- Raw source detail drawer/page。
- 来源版本历史和 hash 变化展示。
- 原始源可读预览：文本、Markdown、HTML、代码、Office 抽取摘要。
- 知识树筛选、节点类型标识、来源关联。
- 知识图谱边类型：共享来源、主题、内链、实体。
- 导入后的任务状态和失败重试。

**分工**

- A：来源详情 API、版本历史 API、任务状态模型。
- B：Raw 详情、Wiki 树和图谱交互。
- C：导入/版本/图谱 smoke tests 和文档。

**验收**

- 导入 PDF、网页、代码、Excel、Word 后能看到来源状态和预览。
- quarantined 来源不会进入 wiki_sections。
- Wiki 页面可点开每篇文章并显示关联关系。

### M3：安全与治理增强（第 3 周）

**目标**：把安全和治理做成企业可验收能力。

**范围**

- 来源风险策略分级：block/warn/info。
- source review 工作流：quarantine、approve、restore、comment。
- token scope 细化：read/admin/operator。
- 审计事件筛选和导出。
- readiness gate 增加安全证据链接。
- release bundle manifest 增加 hash 和生成者。

**分工**

- A：风险策略、审计模型、token scope。
- B：Governance/Audit UI 筛选和详情。
- C：安全测试题组、release bundle 验收脚本。

**验收**

- 高危命令、敏感文件、prompt injection、私网 URL 均有可见审计证据。
- read token 无法执行 admin 动作。
- release bundle manifest 可追溯。

### M4：工作台与 LLM 配置成熟化（第 4 周）

**目标**：把问答、解释、演示物生成和 LLM 配置变成可日常使用工作台。

**范围**

- Ask 支持历史记录和证据展开。
- Explain 展示 route、safety、evidence、source status。
- Workbench 支持演示物、Markdown brief、HTML outline 多产物。
- Agents 支持测试连接、模型路由预览、配置回滚。
- Agents 页面可对单个 agent 发起连接诊断，结果写入审计。
- LLM 调用超时、失败、降级策略可见。

**分工**

- A：LLM router、fallback、配置版本。
- B：Ask/Workbench/Agents 交互。
- C：LLM mock tests、配置文档、skill 示例。

**验收**

- opencode + DeepSeek/Hermes 配置可保存、测试、回滚。
- LLM 不可用时 deterministic fallback 明确。
- 生成物下载和审计记录一致。

### M5：发布与生产化（第 5 周）

**目标**：形成可交付版本和运维手册。

**范围**

- 版本号和 tag 策略。
- Linux/Windows CLI release artifact。
- 部署手册：本地、server、systemd/launchd。
- 备份恢复：`.state/wiki.sqlite`、`docs/`、`wiki/`、`output/`。
- 性能基线：导入 100/1000 文件、问答延迟、编译耗时。
- 安全配置模板：企业默认 `Permission.json` 和 `.env.example`。

**分工**

- A：部署、安全配置、备份恢复。
- B：生产模式 UI polish、空态/错误态。
- C：release artifact、性能脚本、发布说明。

**验收**

- tag release 可生成 CLI artifact 和 release bundle。
- 新机器按文档能启动服务、导入资料、运行问答。
- 性能和安全基线有记录。

---

## 10. 研发流程

### 10.1 分支策略

- `main`：始终可运行，所有交付从 main 发布。
- `feature/<area>-<summary>`：功能开发。
- `fix/<area>-<summary>`：缺陷修复。
- `docs/<summary>`：文档更新。

### 10.2 PR 要求

每个 PR 必须包含：

- 变更范围说明
- 影响模块
- 验证命令和结果
- UI 变更截图或说明
- 安全/鉴权影响说明
- 是否需要迁移数据

### 10.3 Review 规则

- API/schema/security 变更：A + C 必须 review，B 确认可见状态。
- UI 变更：B 主审，A 确认 API，C 确认测试。
- CLI/skill/release 变更：C 主审，A 确认 API，B 确认文案。
- 文档变更：至少 1 人 review；涉及安全或发布时 2 人 review。

### 10.4 Definition of Done

一个功能完成必须满足：

- API/CLI/Web 行为一致。
- 有至少一条自动化或 smoke 验证。
- 有审计或错误状态。
- 文档更新。
- 不引入旧品牌、旧路径或 RAG 表述。
- `main` 可运行，工作区无未提交变更。

---

## 11. 验证矩阵

| 类型 | 命令/动作 | 负责人 | 频率 |
| --- | --- | --- | --- |
| Python 语法 | `python3 -m compileall -q work` | C | 每 PR |
| API contract | `PYTHONPATH=work python3 -m stonehenge_wiki.contract_checks` | A/C | 每 PR |
| 平台 smoke | `PYTHONPATH=work python3 -m unittest discover -s work/tests -q` | C | 每 PR |
| Rust fmt | `cargo fmt --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml --check` | C | 每 PR |
| Rust CLI | `cargo test --manifest-path work/skills/stonehenge-wiki/cli/Cargo.toml` | C | 每 PR |
| Skill build | `./work/skills/stonehenge-wiki/scripts/build_skill_cli.sh` | C | 每 PR |
| REST health | `./work/skills/stonehenge-wiki/bin/stonehenge-wiki --health` | A/C | 每 PR |
| Browser smoke | 打开 `http://127.0.0.1:8765/` 检查主要页面 | B | UI PR |
| Security smoke | 高危命令/敏感文件/prompt injection | A/C | 安全 PR |
| Release smoke | readiness + evaluation + release bundle | C | 里程碑 |

---

## 12. 风险清单

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 文档和实现漂移 | 新成员误用旧命令 | 每个 PR 更新 docs，CI 加 smoke |
| CLI 绕过 REST | 安全规则分叉 | Rust CLI REST-only，测试 help 和行为 |
| Office 解析不稳定 | 导入结果不完整 | soffice 可选增强，抽取失败进入风险报告 |
| LLM 配置不可用 | 问答质量下降 | deterministic fallback、LLM 状态可见 |
| 来源敏感信息扩散 | 安全事故 | release bundle 排除 docs/sqlite，source risk scanner |
| 前端状态不可见 | 用户误判执行结果 | 所有动作有 loading/success/fail |
| SQLite schema 演进 | 旧数据不可读 | schema version + migration plan |
| 3 人并行冲突 | 重复实现或互相覆盖 | 模块 owner + PR review 规则 |

---

## 13. 文档体系

| 文档 | 用途 | Owner |
| --- | --- | --- |
| `DESIGN.md` | 项目级蓝图、分工、里程碑 | C |
| `work/stonehenge_wiki/DESIGN.md` | 平台内部架构和模块说明 | A |
| `INSTRUCTION.md` | 运行、CLI、API、skill 使用说明 | C |
| `stonehenge-wiki/README.md` | 数据目录和评测数据说明 | C |
| `stonehenge-wiki/AGENTS.md` | compiled wiki schema 和维护契约 | A/C |
| `work/skills/stonehenge-wiki/SKILL.md` | Codex skill 使用方式 | C |
| `CONTRIBUTING.md` | 3 人协作、PR、review 和验证规范 | C |
| `CHANGELOG.md` | 版本变更记录 | C |

---

## 14. 近期行动列表

### P0

- 给 REST API route contract 增加更深的 scope/schema 一致性检查。
- 给 README/INSTRUCTION/DESIGN 增加一致性检查脚本。
- 扩展 GitHub Actions，增加 release bundle 和 browser smoke 的可选门禁。

### P1

- Raw 来源详情和版本历史 UI。
- Wiki 图谱边类型增强。
- Release bundle manifest。
- GitHub Actions。

### P2

- 后台任务队列。
- 多租户 token scope。
- compiled wiki diff 和回滚。
- 性能基线和压测样本。
