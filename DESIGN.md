# LLM-Wiki-System 系统规划

## 调研摘要

当前主流 LLM Wiki 类系统大致分为三类：

- 编译型 wiki：以 Karpathy 的 LLM Wiki 为代表，核心是 raw sources、generated wiki、schema 三层，把一次性上下文拼接改成可维护的知识页。
- 笔记型研究工作台：NotebookLM 类产品强调资料导入、问答、摘要、演示稿/讲稿等知识工作流入口。
- 企业知识运营台：Dify、AnythingLLM、WeKnora 等系统提供多格式导入、权限、审计、会话、API 和可视化管理。

本题的核心风险是评测输出严格 JSON、批注修复需要落文件、问题里和文档里都可能有注入/高危命令。因此本实现采用“原始资料索引 + 编译型 Markdown wiki + schema 约束 + 安全网关前置”的架构，而不是默认把问题交给通用聊天模型。

Karpathy 的 LLM Wiki 模式强调三层：raw sources、LLM-generated wiki、schema。当前项目据此新增编译型 Markdown wiki：`docs/` 是 raw sources，`wiki/` 是生成知识层，`AGENTS.md` 是 schema/维护契约。系统不引入向量库、原文切片表或外置检索生成层；可搜索对象是编译后的 wiki 页面和章节。

参考入口：

- Karpathy LLM Wiki: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f
- Dify knowledge base docs: https://docs.dify.ai/en/guides/knowledge-base
- AnythingLLM docs: https://docs.anythingllm.com/
- WeKnora repository: https://github.com/Tencent/WeKnora

## 企业级落地架构

```text
CLI / Skill / HTTP API / Web Console
        |
        v
LLMWikiPlatform
        |
        +--> PlatformConfig: config.json + 环境变量
        +--> PermissionGuard: Permission.json + 高危意图拦截
        +--> WikiIndex: 动态文档索引
        +--> QuestionAnswerer: 严格格式回答
        +--> SQLiteStore: files/comments/wiki_sections/audit_events/job_runs
        +--> Repair/Execution: 受控修复与受限代码运行
        |
        v
output/group-x-answer.md / output/fixed / .state/wiki.sqlite
        |
        v
wiki/index.md / wiki/sources / wiki/topics / wiki/log.md
```

## 关键设计

- 不依赖 `docs/` 物理归档判断业务类型；所有文件会深度遍历，并基于正文关键词动态打标签。
- Office 文档用标准库 zip/xml 优先解析；Excel 在安装 `openpyxl` 时读取单元格和批注，并可生成简单透视图工作簿。
- 批注解析兼容 `todo/to/end_date` 的大小写、中英文冒号和不规则分隔。
- 所有答案统一走 `make_standard_response`，避免各业务分支输出格式漂移。
- 代码执行只支持安全子集：Python 先 AST 检查，再隔离临时目录短超时运行；JS/Java 也做危险 API 静态阻断。
- Skill 和 HTTP API 不重新实现逻辑，只调用平台服务，确保所有入口的安全、审计和格式一致。
- SQLite 保存可重建索引、批注元数据、来源注册表、metadata-only 来源版本历史、wiki 章节索引、审计事件和任务运行记录，不复制原始文档正文，降低敏感内容扩散风险。
- API 支持可选分级 token 鉴权：`LLM_WIKI_READ_TOKEN` 可读索引、审计和问答，`LLM_WIKI_API_TOKEN` 具备管理权限，可导入、重建、编译和生成文件。
- 受控导入通道把本地文件或公开 URL 复制到 `docs/<category>/` 后重建索引，阻断私网 URL、超大文件、未知扩展和权限配置拒绝的路径。
- 治理报告汇总来源状态、TODO 到期风险、阻断审计和任务历史，可通过 API/CLI 查看并导出 Markdown。
- Markdown wiki 编译层把原始文档转成可读、可 lint、可被 agent 维护的知识页；章节搜索只读 `wiki/` 编译层，避免退回到原始文档切片。
- 独立问答解释通道返回检索路由、匹配词、命中文件、证据片段和安全判定，不改变题组答案的严格 JSON schema。
- 质量评估报告批量运行题组，检查严格答案 schema、证据覆盖、安全阻断、空答案、LLM 使用和来源引用，用于回归验收。

## 平台模块

- `config.py`：加载 `llm-wiki/config.json`，控制状态目录、数据库、API 和审计。
- `store.py`：SQLite 持久化层，保存索引快照、批注表、来源注册表、来源版本历史、wiki 章节索引、审计事件和任务运行结果。
- `platform.py`：企业级服务门面，统一 CLI、skill、API 调用路径。
- `importer.py`：受控知识源导入，处理 URL/文件读取、扩展名白名单、目录规范化、去重命名和 SSRF 防护。
- `reports.py`：治理报告生成器，输出 JSON 摘要和 Markdown 报告。
- `source_risk.py`：来源风险扫描器，检查提示注入、Permission 命中、密钥位置、危险代码、抽取失败和 TODO 风险。
- `evaluation.py`：题组质量评估器，输出 schema、证据、安全和 LLM 使用指标。
- `server.py`：标准库 HTTP API，适合评测环境零依赖运行。
- `cli_io.py`：题组 JSON 读取、输出路径和自验证日志。
- `office_bridge.py`：可选 LibreOffice/soffice 转换层，用于 `.doc/.ppt/.xls` 老式 Office 文件索引和修复；不可用时安全降级到二进制文本兜底。
- `web/`：零依赖浏览器控制台，提供健康状态、查询、题组运行、文件/批注库存和审计视图。
- `wiki_compiler.py`：生成 `wiki/index.md`、`wiki/sources/*.md`、`wiki/topics/*.md`、`wiki/log.md`，并检查缺失页、陈旧页和坏链。
- `wiki_sections.py`：从编译后的 `wiki/` 页面抽取章节级索引，过滤密钥和提示注入文本，为 CLI/API 控制台提供 wiki 层搜索。
