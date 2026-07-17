# Changelog

所有重要变更都记录在这里。版本发布以 Git tag 和 GitHub release 为准。

## Unreleased

- 扩展项目级设计文档，补齐三人协作分工、里程碑、验证矩阵、风险清单和成熟项目路线图。
- 增加贡献规范，明确分支、PR、review、验证和禁止事项。
- 增加 OpenCode 独立 LLM agent 配置脚本，支持保留判题平台预配置或通过环境变量安全注入 GLM-5.2 凭证。
- 增加比赛级 Agent harness：固定格式确定性解析，整组题目由受限 OpenCode 子 Agent 批量裁决，知识问答与自由批注修复走严格 JSON 契约。
- 强化 Permission、提示注入、代码执行与符号链接边界；黑名单文件不会被解析、哈希、下载、透视或修复流程读取。
- 增加公开 8 题精确回归、210 文件/20 题规模回归、5 路并发稳定性回归与严格答案验证器。
- 增加精确命名的比赛 ZIP allowlist 打包器、秘密扫描与反向结构验证。
- 增加 LLM agent 连接诊断：`POST /llm/test`、Rust CLI `--test-llm-agent`、Agents 页面测试按钮和审计记录。
- 增加 Raw 来源详情：`GET /sources/detail`、Rust CLI `--source-detail`、同页脱敏抽取预览、版本、审核、风险和 wiki 区段。
- 增加机器可读 API 契约 v2：`GET /api/contract`、Python 兼容 CLI `--api-contract`、Rust REST CLI `--api-contract`，包含 query/body 字段 required/type/alias/enum 元数据。
- 增加 API contract 一致性检查和 GitHub Actions CI，覆盖 Python compile、route/scope/query/body 字段元数据/CLI contract、unittest、Rust fmt/test 和 skill CLI build。
- 增加文档一致性校验脚本 `scripts/check_doc_consistency.py`：自动校验 `README/INSTRUCTION/DESIGN` 中出现的 CLI flag 与 API 路径与 `api_contract.py` / CLI 实现保持一致。
- 增强 release bundle manifest，可追踪生成者、artifact 数量、每个打包文件的 size/sha256，以及发布包自身 sha256。
- 增加 GitHub PR 模板和 Bug/Feature issue forms，固化 3 人协作分工、验证命令、安全影响和 no-RAG/REST-only guardrails。
- 升级 GitHub Actions `checkout`/`setup-python` major 版本，清理 Node 20 deprecation annotation，并增加 workflow 版本守护测试。

## 0.1.0

- 完成 Stonehenge Wiki 基线：REST API、Web Console、REST CLI wrapper、compiled wiki、source governance、readiness/evaluation/release bundle。
- 统一品牌为 Stonehenge Wiki，并添加 `SW` favicon。
