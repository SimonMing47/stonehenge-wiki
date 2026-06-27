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

## 落地架构

```text
question/group-x.md
        |
        v
安全网关 PermissionGuard
        |
        v
动态文件索引 WikiIndex
        |
        +--> Office/代码/TODO 批注解析
        +--> 文件类型统计
        +--> 关键词/标签检索
        +--> 受限代码运行
        +--> 批注修复落盘
        |
        v
Answer 格式化工厂
        |
        v
output/group-x-answer.md
```

## 关键设计

- 不依赖 `docs/` 物理归档判断业务类型；所有文件会深度遍历，并基于正文关键词动态打标签。
- Office 文档用标准库 zip/xml 优先解析；Excel 在安装 `openpyxl` 时读取单元格和批注，并可生成简单透视图工作簿。
- 批注解析兼容 `todo/to/end_date` 的大小写、中英文冒号和不规则分隔。
- 所有答案统一走 `make_standard_response`，避免各业务分支输出格式漂移。
- 代码执行只支持安全子集：Python 先 AST 检查，再隔离临时目录短超时运行；JS/Java 也做危险 API 静态阻断。
- Skill 不重新实现逻辑，只调用 CLI，确保 CLI 与 skill 输出一致。

