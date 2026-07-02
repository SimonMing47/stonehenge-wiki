# Changelog

所有重要变更都记录在这里。版本发布以 Git tag 和 GitHub release 为准。

## Unreleased

- 扩展项目级设计文档，补齐三人协作分工、里程碑、验证矩阵、风险清单和成熟项目路线图。
- 增加贡献规范，明确分支、PR、review、验证和禁止事项。
- 增加 opencode 独立 LLM agent 配置说明和 skill 级 Hermes 配置脚本，复用本机 Hermes DeepSeek API 并完成 opencode/服务端双层验证。
- 增加 LLM agent 连接诊断：`POST /llm/test`、Rust CLI `--test-llm-agent`、Agents 页面测试按钮和审计记录。
- 增加 Raw 来源详情：`GET /sources/detail`、Rust CLI `--source-detail`、同页脱敏抽取预览、版本、审核、风险和 wiki 区段。
- 增加机器可读 API 契约：`GET /api/contract`、Python 兼容 CLI `--api-contract`、Rust REST CLI `--api-contract`。
- 增加 API contract 一致性检查和 GitHub Actions CI，覆盖 Python compile、route/scope/query/body/CLI contract、unittest、Rust fmt/test 和 skill CLI build。
- 增强 release bundle manifest，可追踪生成者、artifact 数量、每个打包文件的 size/sha256，以及发布包自身 sha256。
- 增加 GitHub PR 模板和 Bug/Feature issue forms，固化 3 人协作分工、验证命令、安全影响和 no-RAG/REST-only guardrails。
- 升级 GitHub Actions `checkout`/`setup-python` major 版本，清理 Node 20 deprecation annotation，并增加 workflow 版本守护测试。

## 0.1.0

- 完成 Stonehenge Wiki 基线：REST API、Web Console、Rust REST CLI、Codex skill、compiled wiki、source governance、readiness/evaluation/release bundle。
- 统一品牌为 Stonehenge Wiki，并添加 `SW` favicon。
