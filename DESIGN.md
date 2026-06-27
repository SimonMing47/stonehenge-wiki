# LLM-Wiki-System 系统规划

## 调研摘要

当前主流 LLM-wiki/RAG 系统大致分为三类：

- 平台型知识库：Dify、RAGFlow、AnythingLLM，通常提供数据集管理、文档解析、切片、向量检索、会话和 API。
- 框架型 RAG：LlamaIndex、Haystack，强调 connector、index/retriever、pipeline、generator 的可组合实现。
- 图谱增强型 RAG：Microsoft GraphRAG，用实体/关系图谱增强跨文档推理和全局查询。

本题的核心风险是评测输出严格 JSON、批注修复需要落文件、问题里和文档里都可能有注入/高危命令。因此本实现采用“确定性解析索引 + 规则检索回答 + 安全网关前置”的架构，而不是默认把问题交给通用聊天模型。

参考入口：

- Microsoft GraphRAG: https://microsoft.github.io/graphrag/
- LlamaIndex docs: https://docs.llamaindex.ai/en/stable/
- Haystack docs: https://docs.haystack.deepset.ai/docs/intro
- RAGFlow repository: https://github.com/infiniflow/ragflow
- Dify knowledge base docs: https://docs.dify.ai/en/guides/knowledge-base
- AnythingLLM docs: https://docs.anythingllm.com/

## 企业级落地架构

```text
CLI / Skill / HTTP API
        |
        v
LLMWikiPlatform
        |
        +--> PlatformConfig: config.json + 环境变量
        +--> PermissionGuard: Permission.json + 高危意图拦截
        +--> WikiIndex: 动态文档索引
        +--> QuestionAnswerer: 严格格式回答
        +--> SQLiteStore: files/comments/audit_events/job_runs
        +--> Repair/Execution: 受控修复与受限代码运行
        |
        v
output/group-x-answer.md / output/fixed / .state/wiki.sqlite
```

## 关键设计

- 不依赖 `docs/` 物理归档判断业务类型；所有文件会深度遍历，并基于正文关键词动态打标签。
- Office 文档用标准库 zip/xml 优先解析；Excel 在安装 `openpyxl` 时读取单元格和批注，并可生成简单透视图工作簿。
- 批注解析兼容 `todo/to/end_date` 的大小写、中英文冒号和不规则分隔。
- 所有答案统一走 `make_standard_response`，避免各业务分支输出格式漂移。
- 代码执行只支持安全子集：Python 先 AST 检查，再隔离临时目录短超时运行；JS/Java 也做危险 API 静态阻断。
- Skill 和 HTTP API 不重新实现逻辑，只调用平台服务，确保所有入口的安全、审计和格式一致。
- SQLite 只保存可重建索引、批注元数据、审计事件和任务运行记录，不复制原始文档正文，降低敏感内容扩散风险。
- API 支持可选 token 鉴权：设置 `LLM_WIKI_API_TOKEN` 后，请求需携带 `X-LLM-WIKI-TOKEN`。

## 平台模块

- `config.py`：加载 `llm-wiki/config.json`，控制状态目录、数据库、API 和审计。
- `store.py`：SQLite 持久化层，保存索引快照、批注表、审计事件和任务运行结果。
- `platform.py`：企业级服务门面，统一 CLI、skill、API 调用路径。
- `server.py`：标准库 HTTP API，适合评测环境零依赖运行。
- `cli_io.py`：题组 JSON 读取、输出路径和自验证日志。
- `office_bridge.py`：可选 LibreOffice/soffice 转换层，用于 `.doc/.ppt/.xls` 老式 Office 文件索引和修复；不可用时安全降级到二进制文本兜底。
